"""Resolve temporal/conflicting FactState records in HydraDB."""

from __future__ import annotations

import argparse
import gc
import json
import os
import re
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from hydra_db import HydraDB


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


DATABASE_NAME = "hackhydra-track1"
PAGE_SIZE = 100
AUTHORITY_WEIGHTS: dict[str, dict[str, float]] = {
    "github": {"status": 0.9, "*": 0.7},
    "jira": {"status": 0.85, "*": 0.6},
    "gmail": {"*": 0.4},
    "fireflies": {"*": 0.5},
}
AUTHORITY_MARGIN = 0.15
VALID_TO_SENTINEL = 9_999_999_999
USE_LEARNED_AUTHORITY = False


@dataclass
class CascadeDecision:
    group_key: tuple[str, str]
    method: str
    current_ids: list[str]
    superseded_ids: list[str]
    disputed_ids: list[str]
    reasoning: str
    fact_summaries: list[dict[str, Any]]


def load_dotenv(path: Path = PROJECT_ROOT / ".env") -> None:
    if not path.exists():
        return
    with path.open(encoding="utf-8") as env_file:
        for line in env_file:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def get_api_key() -> str:
    load_dotenv()
    api_key = os.environ.get("HYDRADB_API_KEY")
    if not api_key:
        raise RuntimeError("HYDRADB_API_KEY environment variable is required.")
    return api_key


def to_plain_data(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return to_plain_data(value.model_dump())
    if hasattr(value, "dict"):
        return to_plain_data(value.dict())
    if isinstance(value, dict):
        return {key: to_plain_data(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_plain_data(item) for item in value]
    if hasattr(value, "__dict__"):
        return to_plain_data(vars(value))
    return value


def metadata(source: dict[str, Any]) -> dict[str, Any]:
    return dict(source.get("metadata") or {})


def additional_metadata(source: dict[str, Any]) -> dict[str, Any]:
    return dict(source.get("additional_metadata") or {})


def list_all_sources(client: HydraDB, database: str, collection: str, page_size: int = PAGE_SIZE) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    page = 1
    while True:
        response = client.context.list(
            database=database,
            collection=collection,
            type="knowledge",
            page=page,
            page_size=page_size,
        )
        data = to_plain_data(response.data)
        page_sources = data.get("sources") or []
        sources.extend(page_sources)
        pagination = data.get("pagination") or {}
        if not pagination.get("has_next"):
            break
        page += 1
    return sources


def fact_value(fact: dict[str, Any]) -> str:
    extra = additional_metadata(fact)
    if "value" in extra:
        return str(extra.get("value") or "")
    meta = metadata(fact)
    return str(meta.get("value") or fact.get("note") or fact.get("title") or "")


def normalize_value(value: str) -> str:
    text = value.lower().strip()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^a-z0-9 ._:/-]+", "", text)
    return text


def value_bucket(value: str, buckets: list[str], threshold: float = 0.92) -> str:
    normalized = normalize_value(value)
    if not normalized:
        return ""
    for bucket in buckets:
        if normalized == bucket:
            return bucket
        if SequenceMatcher(None, normalized, bucket).ratio() >= threshold:
            return bucket
    buckets.append(normalized)
    return normalized


def int_field(value: Any, default: int = 0) -> int:
    if value in (None, ""):
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def fact_valid_from(fact: dict[str, Any]) -> int:
    meta = metadata(fact)
    value = meta.get("valid_from")
    if value not in (None, ""):
        return int_field(value)
    timestamp = fact.get("timestamp")
    if not timestamp:
        return 0
    try:
        parsed = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return int(parsed.timestamp())
    except ValueError:
        return 0


def doc_source_type(fact: dict[str, Any]) -> str:
    meta = metadata(fact)
    extra = additional_metadata(fact)
    return str(
        meta.get("doc_source_type")
        or extra.get("doc_source_type")
        or fact.get("source")
        or ""
    ).lower()


def source_doc_id(fact: dict[str, Any]) -> str:
    meta = metadata(fact)
    extra = additional_metadata(fact)
    return str(meta.get("source_doc_id") or extra.get("source_doc_id") or "")


def authority_weight(fact: dict[str, Any]) -> float:
    meta = metadata(fact)
    if USE_LEARNED_AUTHORITY:
        return float(meta.get("authority_weight") or 0.3)
    source_type = doc_source_type(fact)
    predicate = str(meta.get("predicate") or "").lower()
    source_weights = AUTHORITY_WEIGHTS.get(source_type, {})
    return float(source_weights.get(predicate, source_weights.get("*", 0.3)))


def group_key(fact: dict[str, Any]) -> tuple[str, str]:
    meta = metadata(fact)
    return str(meta.get("subject_id") or ""), str(meta.get("predicate") or "")


def summarize_fact(fact: dict[str, Any]) -> dict[str, Any]:
    meta = metadata(fact)
    return {
        "id": fact.get("id"),
        "subject_id": meta.get("subject_id"),
        "predicate": meta.get("predicate"),
        "value": fact_value(fact),
        "source_doc_id": source_doc_id(fact),
        "doc_source_type": doc_source_type(fact),
        "valid_from": fact_valid_from(fact),
        "authority_weight": authority_weight(fact),
    }


def independent_source_count(facts: list[dict[str, Any]]) -> int:
    source_ids = {source_doc_id(fact) for fact in facts if source_doc_id(fact)}
    return len(source_ids) or len(facts)


def pick_current(facts: list[dict[str, Any]]) -> dict[str, Any]:
    return max(facts, key=lambda fact: (authority_weight(fact), fact_valid_from(fact), fact.get("id", "")))


def decide_group(key: tuple[str, str], facts: list[dict[str, Any]]) -> CascadeDecision:
    sorted_facts = sorted(facts, key=fact_valid_from)
    if len(sorted_facts) == 1:
        current = sorted_facts[0]
        return CascadeDecision(
            group_key=key,
            method="single",
            current_ids=[current["id"]],
            superseded_ids=[],
            disputed_ids=[],
            reasoning="Only one FactState in group; marked current.",
            fact_summaries=[summarize_fact(current)],
        )

    ranked = sorted(sorted_facts, key=authority_weight, reverse=True)
    highest = authority_weight(ranked[0])
    next_highest = authority_weight(ranked[1])
    if highest - next_highest > AUTHORITY_MARGIN:
        current = ranked[0]
        superseded = [fact for fact in sorted_facts if fact["id"] != current["id"]]
        return CascadeDecision(
            group_key=key,
            method="authority",
            current_ids=[current["id"]],
            superseded_ids=[fact["id"] for fact in superseded],
            disputed_ids=[],
            reasoning=(
                f"{current['id']} wins by authority weight {highest:.2f}; "
                f"next highest is {next_highest:.2f}."
            ),
            fact_summaries=[summarize_fact(fact) for fact in sorted_facts],
        )

    buckets: list[str] = []
    by_value: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for fact in sorted_facts:
        by_value[value_bucket(fact_value(fact), buckets)].append(fact)

    value_counts = {
        value: independent_source_count(value_facts)
        for value, value_facts in by_value.items()
    }
    ranked_values = sorted(value_counts.items(), key=lambda item: item[1], reverse=True)
    top_value, top_count = ranked_values[0]
    second_count = ranked_values[1][1] if len(ranked_values) > 1 else 0
    if top_count > second_count:
        winning_facts = by_value[top_value]
        current = pick_current(winning_facts)
        superseded = [fact for fact in sorted_facts if fact["id"] != current["id"]]
        return CascadeDecision(
            group_key=key,
            method="corroboration",
            current_ids=[current["id"]],
            superseded_ids=[fact["id"] for fact in superseded],
            disputed_ids=[],
            reasoning=(
                f"Value bucket {top_value!r} wins with {top_count} independent "
                f"source_doc_ids vs {second_count}."
            ),
            fact_summaries=[summarize_fact(fact) for fact in sorted_facts],
        )

    different_values = len(by_value) > 1
    equal_authority = abs(highest - next_highest) <= AUTHORITY_MARGIN
    equal_corroboration = top_count == second_count
    if len(sorted_facts) == 2 and different_values and equal_authority and equal_corroboration:
        return CascadeDecision(
            group_key=key,
            method="disputed",
            current_ids=[],
            superseded_ids=[],
            disputed_ids=[fact["id"] for fact in sorted_facts],
            reasoning=(
                "Exactly two FactStates disagree with close/equal authority and "
                "equal corroboration; left disputed."
            ),
            fact_summaries=[summarize_fact(fact) for fact in sorted_facts],
        )

    current = max(sorted_facts, key=fact_valid_from)
    superseded = [fact for fact in sorted_facts if fact["id"] != current["id"]]
    return CascadeDecision(
        group_key=key,
        method="recency",
        current_ids=[current["id"]],
        superseded_ids=[fact["id"] for fact in superseded],
        disputed_ids=[],
        reasoning=f"{current['id']} wins by most recent valid_from={fact_valid_from(current)}.",
        fact_summaries=[summarize_fact(fact) for fact in sorted_facts],
    )


def decide_last_write_wins(key: tuple[str, str], facts: list[dict[str, Any]]) -> CascadeDecision:
    sorted_facts = sorted(facts, key=fact_valid_from)
    current = sorted_facts[-1]
    superseded = [fact for fact in sorted_facts if fact["id"] != current["id"]]
    return CascadeDecision(
        group_key=key,
        method="single" if len(sorted_facts) == 1 else "last_write_wins",
        current_ids=[current["id"]],
        superseded_ids=[fact["id"] for fact in superseded],
        disputed_ids=[],
        reasoning=f"{current['id']} wins by latest valid_from={fact_valid_from(current)}.",
        fact_summaries=[summarize_fact(fact) for fact in sorted_facts],
    )


def update_source_metadata(
    client: HydraDB,
    database: str,
    source_id: str,
    meta: dict[str, Any],
    extra: dict[str, Any],
    collection: str | None,
) -> None:
    try:
        client.context.update_source_metadata(
            source_id,
            database=database,
            collection=collection,
            database_metadata=meta,
            additional_metadata=extra,
        )
    except Exception:
        client.context.update_source_metadata(
            source_id,
            database=database,
            collection=collection,
            tenant_metadata=meta,
            additional_metadata=extra,
        )


def apply_decision(
    client: HydraDB,
    database: str,
    collection: str,
    decision: CascadeDecision,
    facts_by_id: dict[str, dict[str, Any]],
    dry_run: bool,
    apply_authority_weight: bool = True,
) -> None:
    current_id = decision.current_ids[0] if decision.current_ids else None
    group_facts = [facts_by_id[fact_id] for fact_id in decision.current_ids + decision.superseded_ids + decision.disputed_ids]
    corroboration_by_value: dict[str, int] = {}
    buckets: list[str] = []
    if apply_authority_weight:
        value_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for fact in group_facts:
            value_groups[value_bucket(fact_value(fact), buckets)].append(fact)
        for bucket, facts in value_groups.items():
            corroboration_by_value[bucket] = independent_source_count(facts)

    for fact in group_facts:
        meta = metadata(fact)
        extra = additional_metadata(fact)
        if apply_authority_weight:
            meta["authority_weight"] = authority_weight(fact)
            meta["corroboration_count"] = corroboration_by_value.get(
                value_bucket(fact_value(fact), buckets),
                1,
            )

        if fact["id"] in decision.current_ids:
            meta["state"] = "current"
            extra.pop("supersedes", None)
        elif fact["id"] in decision.superseded_ids:
            meta["state"] = "superseded"
            extra["supersedes"] = current_id
        elif fact["id"] in decision.disputed_ids:
            meta["state"] = "disputed"
            extra.pop("supersedes", None)

        meta.setdefault("valid_to", VALID_TO_SENTINEL)
        meta.setdefault("txn_to", VALID_TO_SENTINEL)
        if not dry_run:
            update_source_metadata(
                client,
                database,
                fact["id"],
                meta,
                extra,
                collection,
            )


def run_cascade(
    database: str,
    collection: str,
    dry_run: bool,
    limit_groups: int | None,
    disabled: bool = False,
    use_learned_authority: bool = False,
) -> dict[str, Any]:
    global USE_LEARNED_AUTHORITY
    USE_LEARNED_AUTHORITY = use_learned_authority
    client = HydraDB(token=get_api_key())
    all_sources = list_all_sources(client, database, collection)
    fact_states = [
        source
        for source in all_sources
        if metadata(source).get("type") == "FactState"
    ]
    del all_sources
    gc.collect()

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for fact in fact_states:
        key = group_key(fact)
        if key[0] and key[1]:
            grouped[key].append(fact)

    facts_by_id = {fact["id"]: fact for fact in fact_states}
    decisions: list[CascadeDecision] = []
    conflict_groups = 0
    method_counts = CounterLike()

    for key, facts in sorted(grouped.items()):
        if limit_groups is not None and len(decisions) >= limit_groups:
            break
        decision = decide_last_write_wins(key, facts) if disabled else decide_group(key, facts)
        decisions.append(decision)
        method_counts.increment(decision.method)
        if len(facts) > 1:
            conflict_groups += 1
        apply_decision(
            client,
            database,
            collection,
            decision,
            facts_by_id,
            dry_run,
            apply_authority_weight=not disabled and not use_learned_authority,
        )

    return {
        "fact_states_processed": len(fact_states),
        "groups_processed": len(decisions),
        "conflict_groups": conflict_groups,
        "resolved_via_authority": method_counts["authority"],
        "resolved_via_corroboration": method_counts["corroboration"],
        "resolved_via_recency": method_counts["recency"],
        "resolved_via_last_write_wins": method_counts["last_write_wins"],
        "single_fact_groups_marked_current": method_counts["single"],
        "disputed_groups": method_counts["disputed"],
        "use_learned_authority": use_learned_authority,
        "examples": [asdict(decision) for decision in decisions if decision.method != "single"][:3],
    }


class CounterLike(defaultdict[str, int]):
    def __init__(self) -> None:
        super().__init__(int)

    def increment(self, key: str) -> None:
        self[key] += 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Run temporal conflict cascade over HydraDB FactStates.")
    parser.add_argument("--database", default=DATABASE_NAME)
    parser.add_argument("--collection", default="default")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit-groups", type=int, default=None)
    parser.add_argument("--disabled", action="store_true")
    parser.add_argument("--use-learned-authority", action="store_true")
    args = parser.parse_args()

    try:
        summary = run_cascade(
            args.database,
            args.collection,
            args.dry_run,
            args.limit_groups,
            args.disabled,
            args.use_learned_authority,
        )
        print("Temporal conflict cascade summary:")
        print(f"- FactStates processed: {summary['fact_states_processed']}")
        print(f"- groups processed: {summary['groups_processed']}")
        print(f"- groups with conflicts/updates: {summary['conflict_groups']}")
        print(f"- resolved via authority: {summary['resolved_via_authority']}")
        print(f"- resolved via corroboration: {summary['resolved_via_corroboration']}")
        print(f"- resolved via recency: {summary['resolved_via_recency']}")
        print(f"- resolved via last-write-wins: {summary['resolved_via_last_write_wins']}")
        print(f"- left disputed: {summary['disputed_groups']}")
        print(f"- single FactState groups marked current: {summary['single_fact_groups_marked_current']}")
        print(f"- using learned authority weights: {summary['use_learned_authority']}")
        print("Examples:")
        print(json.dumps(summary["examples"], indent=2, default=str))
        return 0
    except Exception as exc:
        print(f"Temporal conflict cascade failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
