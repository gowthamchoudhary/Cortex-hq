"""Learn source reliability from HydraDB FactState agreement patterns."""

from __future__ import annotations

import argparse
import gc
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from hydra_db import HydraDB


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from temporal.conflict_cascade import (  # noqa: E402
    AUTHORITY_WEIGHTS,
    DATABASE_NAME,
    additional_metadata,
    doc_source_type,
    fact_value,
    get_api_key,
    group_key,
    list_all_sources,
    metadata,
    update_source_metadata,
    value_bucket,
)


CONVERGENCE_DELTA = 0.01
INITIAL_RELIABILITY = 0.5


def fact_source_type(fact: dict[str, Any]) -> str:
    return doc_source_type(fact) or "unknown"


def group_fact_values(facts: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    buckets: list[str] = []
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for fact in facts:
        grouped[value_bucket(fact_value(fact), buckets)].append(fact)
    return grouped


def value_confidence(facts: list[dict[str, Any]], reliability: dict[str, float]) -> float:
    source_types = {fact_source_type(fact) for fact in facts}
    miss_probability = 1.0
    for source_type in source_types:
        miss_probability *= 1 - reliability.get(source_type, INITIAL_RELIABILITY)
    return max(0.0, min(1.0, 1 - miss_probability))


def initialize_reliability(fact_states: list[dict[str, Any]]) -> dict[str, float]:
    source_types = sorted({fact_source_type(fact) for fact in fact_states})
    return {source_type: INITIAL_RELIABILITY for source_type in source_types}


def discover_truth(
    grouped: dict[tuple[str, str], list[dict[str, Any]]],
    iterations: int,
    convergence_delta: float,
) -> tuple[dict[str, float], dict[tuple[str, str], dict[str, float]], list[dict[str, Any]]]:
    fact_states = [fact for facts in grouped.values() for fact in facts]
    reliability = initialize_reliability(fact_states)
    value_confidences: dict[tuple[str, str], dict[str, float]] = {}
    history: list[dict[str, Any]] = []

    for round_number in range(1, iterations + 1):
        value_confidences = {}
        source_claim_confidences: dict[str, list[float]] = defaultdict(list)

        for key, facts in grouped.items():
            grouped_values = group_fact_values(facts)
            value_confidences[key] = {
                value: value_confidence(value_facts, reliability)
                for value, value_facts in grouped_values.items()
            }
            for value, value_facts in grouped_values.items():
                confidence = value_confidences[key][value]
                for fact in value_facts:
                    source_claim_confidences[fact_source_type(fact)].append(confidence)

        next_reliability = {}
        for source_type, confidences in source_claim_confidences.items():
            average = sum(confidences) / len(confidences) if confidences else INITIAL_RELIABILITY
            next_reliability[source_type] = max(0.0, min(1.0, average))

        delta = max(
            (
                abs(next_reliability.get(source_type, 0.0) - reliability.get(source_type, 0.0))
                for source_type in set(reliability) | set(next_reliability)
            ),
            default=0.0,
        )
        reliability = next_reliability
        history.append({"round": round_number, "max_delta": delta, "reliability": dict(reliability)})
        if delta < convergence_delta:
            break

    return reliability, value_confidences, history


def old_weights_for_source(source_type: str) -> dict[str, float]:
    return AUTHORITY_WEIGHTS.get(source_type, {"*": 0.3})


def update_fact_authority_weights(
    client: HydraDB,
    database: str,
    collection: str,
    fact_states: list[dict[str, Any]],
    reliability: dict[str, float],
    dry_run: bool,
) -> int:
    updated = 0
    for fact in fact_states:
        source_type = fact_source_type(fact)
        meta = metadata(fact)
        extra = additional_metadata(fact)
        meta["authority_weight"] = reliability.get(source_type, INITIAL_RELIABILITY)
        if not dry_run:
            update_source_metadata(
                client,
                database,
                fact["id"],
                meta,
                extra,
                collection,
            )
        updated += 1
    return updated


def example_groups(
    grouped: dict[tuple[str, str], list[dict[str, Any]]],
    value_confidences: dict[tuple[str, str], dict[str, float]],
    limit: int = 3,
) -> list[dict[str, Any]]:
    examples = []
    for key, facts in grouped.items():
        values = value_confidences.get(key, {})
        if len(values) < 2:
            continue
        examples.append(
            {
                "group": {"subject_id": key[0], "predicate": key[1]},
                "value_confidences": values,
                "assertions": [
                    {
                        "fact_id": fact.get("id"),
                        "source_type": fact_source_type(fact),
                        "value": fact_value(fact),
                    }
                    for fact in facts
                ],
            }
        )
        if len(examples) >= limit:
            break
    return examples


def run_truth_discovery(
    database: str,
    collection: str,
    dry_run: bool,
    iterations: int,
    convergence_delta: float,
) -> dict[str, Any]:
    client = HydraDB(token=get_api_key())
    all_sources = list_all_sources(client, database, collection)
    fact_states = [source for source in all_sources if metadata(source).get("type") == "FactState"]
    del all_sources
    gc.collect()

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for fact in fact_states:
        key = group_key(fact)
        if key[0] and key[1]:
            grouped[key].append(fact)

    reliability, value_confidences, history = discover_truth(grouped, iterations, convergence_delta)
    updated = update_fact_authority_weights(client, database, collection, fact_states, reliability, dry_run)

    comparison = {
        source_type: {
            "learned_reliability": reliability[source_type],
            "old_hardcoded_weights": old_weights_for_source(source_type),
        }
        for source_type in sorted(reliability)
    }

    return {
        "fact_states_processed": len(fact_states),
        "groups_processed": len(grouped),
        "rounds_run": len(history),
        "converged": bool(history and history[-1]["max_delta"] < convergence_delta),
        "dry_run": dry_run,
        "fact_states_updated": 0 if dry_run else updated,
        "comparison": comparison,
        "history": history,
        "examples": example_groups(grouped, value_confidences),
    }


def print_comparison(comparison: dict[str, dict[str, Any]]) -> None:
    print("Learned reliability vs old hardcoded weights:")
    for source_type, row in comparison.items():
        old_weights = ", ".join(
            f"{predicate}={weight:.2f}"
            for predicate, weight in sorted(row["old_hardcoded_weights"].items())
        )
        print(f"- {source_type}: learned={row['learned_reliability']:.3f} | old: {old_weights}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Learn source reliability from FactState agreement.")
    parser.add_argument("--database", default=DATABASE_NAME)
    parser.add_argument("--collection", default="default")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--iterations", type=int, default=8)
    parser.add_argument("--convergence-delta", type=float, default=CONVERGENCE_DELTA)
    args = parser.parse_args()

    try:
        if args.iterations < 1:
            raise ValueError("--iterations must be at least 1.")
        summary = run_truth_discovery(
            database=args.database,
            collection=args.collection,
            dry_run=args.dry_run,
            iterations=args.iterations,
            convergence_delta=args.convergence_delta,
        )
        print("Truth discovery summary:")
        print(f"- FactStates processed: {summary['fact_states_processed']}")
        print(f"- groups processed: {summary['groups_processed']}")
        print(f"- rounds run: {summary['rounds_run']}")
        print(f"- converged: {summary['converged']}")
        print(f"- dry run: {summary['dry_run']}")
        print(f"- FactStates updated: {summary['fact_states_updated']}")
        print_comparison(summary["comparison"])
        print("Example conflicting groups:")
        print(json.dumps(summary["examples"], indent=2, default=str))
        print("After writing learned weights, re-run conflict_cascade.py with --use-learned-authority.")
        return 0
    except Exception as exc:
        print(f"Truth discovery failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
