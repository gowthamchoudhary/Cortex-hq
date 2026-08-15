"""Compare graph reasoning configurations on one fixed question sample."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval.baseline import load_dotenv, load_questions, resolve_questions_path  # noqa: E402
from eval.run_system_eval import (  # noqa: E402
    DEFAULT_COLLECTION,
    calculate_accuracy,
    evaluate_questions,
)
from reasoning.answer_question import DATABASE_NAME  # noqa: E402


DEFAULT_LIMIT = 30
DEFAULT_RESULTS_PATH = PROJECT_ROOT / "eval" / "results" / "ablation_table.json"
ABLATION_CONFIGS: dict[str, dict[str, bool]] = {
    "full_system": {},
    # Requires answer_question(ignore_entity_merges=True); this bypasses canonical
    # redirection through merged_into and treats linked entities as raw/unmerged.
    "no_entity_resolution": {"ignore_entity_merges": True},
    "no_graph_reasoning": {"disable_graph_reasoning": True},
    "no_abstention": {"disable_abstention": True},
}


def comparison_rows(
    accuracies: dict[str, dict[str, Any]],
    metric: str,
) -> tuple[list[str], dict[str, dict[str, float]]]:
    categories = sorted(
        {
            category
            for accuracy in accuracies.values()
            for category in accuracy["categories"]
        }
    )
    rows = categories + ["overall"]
    values: dict[str, dict[str, float]] = {}
    for row in rows:
        values[row] = {}
        for config_name, accuracy in accuracies.items():
            source = accuracy["overall"] if row == "overall" else accuracy["categories"].get(row)
            values[row][config_name] = float(source[metric]) if source else 0.0
    return rows, values


def print_comparison_table(
    accuracies: dict[str, dict[str, Any]],
    metric: str,
) -> None:
    rows, values = comparison_rows(accuracies, metric)
    config_names = list(accuracies)
    print(f"{metric.replace('_', ' ').title()} accuracy comparison:")
    print(f"{'category':<24}" + "".join(f"{name:>24}" for name in config_names))
    for row in rows:
        print(f"{row:<24}" + "".join(f"{values[row][name]:>24.3f}" for name in config_names))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run fixed-sample system ablations.")
    parser.add_argument("--questions", type=Path, default=None)
    parser.add_argument("--results-path", type=Path, default=DEFAULT_RESULTS_PATH)
    parser.add_argument("--database", default=DATABASE_NAME)
    parser.add_argument("--collection", default=DEFAULT_COLLECTION)
    parser.add_argument("--provider", choices=("auto", "groq", "openai"), default="auto")
    parser.add_argument("--model", default=None)
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=f"Fixed number of questions used by every configuration (default: {DEFAULT_LIMIT}).",
    )
    parser.add_argument("--timeout-seconds", type=int, default=90)
    args = parser.parse_args()

    if args.limit < 1:
        raise ValueError("--limit must be at least 1")

    load_dotenv()
    questions_path = resolve_questions_path(args.questions)
    questions = load_questions(questions_path)[: args.limit]
    print(
        f"Running the same fixed sample of {len(questions)} questions across "
        f"{len(ABLATION_CONFIGS)} configurations from {questions_path}"
    )

    runs: dict[str, list[dict[str, Any]]] = {}
    accuracies: dict[str, dict[str, Any]] = {}
    for config_name, flags in ABLATION_CONFIGS.items():
        print(f"\nStarting configuration: {config_name} ({flags or 'no flags disabled'})")
        results = evaluate_questions(
            questions=questions,
            database=args.database,
            collection=args.collection,
            provider=args.provider,
            model=args.model,
            timeout_seconds=args.timeout_seconds,
            run_name=config_name,
            **flags,
        )
        runs[config_name] = results
        accuracies[config_name] = calculate_accuracy(results)

    print()
    print_comparison_table(accuracies, "strict")
    print()
    print_comparison_table(accuracies, "partial_credit")

    payload = {
        "questions_path": str(questions_path),
        "question_count": len(questions),
        "question_ids": [question["question_id"] for question in questions],
        "database": args.database,
        "collection": args.collection,
        "configurations": ABLATION_CONFIGS,
        "accuracy": accuracies,
        "runs": runs,
    }
    args.results_path.parent.mkdir(parents=True, exist_ok=True)
    args.results_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print()
    print(f"Saved full ablation comparison to {args.results_path}")


if __name__ == "__main__":
    main()