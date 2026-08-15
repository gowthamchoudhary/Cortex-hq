"""Evaluate the graph reasoning pipeline against the benchmark questions."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval.baseline import (  # noqa: E402
    judge_answer,
    load_dotenv,
    load_questions,
    resolve_questions_path,
)
from reasoning.answer_question import (  # noqa: E402
    DATABASE_NAME,
    answer_question as run_answer_question,
)


DEFAULT_COLLECTION = "benchmark-eval"
DEFAULT_RESULTS_PATH = PROJECT_ROOT / "eval" / "results" / "system_run.json"
DEFAULT_BASELINE_RESULTS_PATH = PROJECT_ROOT / "eval" / "results" / "baseline_run.json"


def summarize(results: list[dict[str, Any]]) -> None:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for result in results:
        grouped[result["category"]].append(result)

    print("Per-category accuracy:")
    for category in sorted(grouped):
        items = grouped[category]
        yes_count = sum(1 for item in items if item["score"] == "yes")
        partial_count = sum(1 for item in items if item["score"] == "partial")
        strict_accuracy = yes_count / len(items)
        partial_credit_accuracy = (yes_count + 0.5 * partial_count) / len(items)
        print(
            f"- {category}: strict={strict_accuracy:.3f} "
            f"partial_credit={partial_credit_accuracy:.3f} n={len(items)}"
        )

    yes_count = sum(1 for item in results if item["score"] == "yes")
    partial_count = sum(1 for item in results if item["score"] == "partial")
    strict_accuracy = yes_count / len(results) if results else 0.0
    partial_credit_accuracy = (yes_count + 0.5 * partial_count) / len(results) if results else 0.0
    print()
    print(
        f"Overall accuracy: strict={strict_accuracy:.3f} "
        f"partial_credit={partial_credit_accuracy:.3f} n={len(results)}"
    )


def evidence_doc_ids(answer_result: dict[str, Any]) -> list[str]:
    evidence = answer_result.get("evidence") or []
    if evidence:
        return [str(doc_id) for doc_id in evidence if doc_id]

    debug = answer_result.get("debug") or {}
    packet = debug.get("context_packet") or {}
    return [str(doc_id) for doc_id in packet.get("evidence_doc_ids") or [] if doc_id]


def load_baseline_results(path: Path = DEFAULT_BASELINE_RESULTS_PATH) -> list[dict[str, Any]] | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else None


def print_abstention_summary(
    results: list[dict[str, Any]],
    baseline_results: list[dict[str, Any]] | None,
) -> None:
    system_abstentions = sum(1 for result in results if result["abstained"])
    system_rate = system_abstentions / len(results) if results else 0.0
    print()
    print(
        f"System abstentions: {system_abstentions}/{len(results)} "
        f"(rate={system_rate:.3f})"
    )
    if baseline_results is None:
        print("Baseline comparison unavailable: eval/results/baseline_run.json was not found.")
        return

    baseline_answered = len(baseline_results)
    baseline_total = len(baseline_results)
    print(
        f"Baseline answered questions: {baseline_answered}/{baseline_total} "
        "(baseline results have no abstention field)"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the graph reasoning pipeline.")
    parser.add_argument("--questions", type=Path, default=None)
    parser.add_argument("--results-path", type=Path, default=DEFAULT_RESULTS_PATH)
    parser.add_argument("--database", default=DATABASE_NAME)
    parser.add_argument("--collection", default=DEFAULT_COLLECTION)
    parser.add_argument("--provider", choices=("auto", "groq", "openai"), default="auto")
    parser.add_argument("--model", default=None)
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional question limit, for example --limit 50. Defaults to all questions.",
    )
    parser.add_argument("--timeout-seconds", type=int, default=90)
    parser.add_argument("--disable-abstention", action="store_true")
    parser.add_argument("--disable-graph-reasoning", action="store_true")
    args = parser.parse_args()

    load_dotenv()
    questions_path = resolve_questions_path(args.questions)
    questions = load_questions(questions_path)
    if args.limit is not None:
        questions = questions[: args.limit]

    limit_label = "no limit" if args.limit is None else f"limit={args.limit}"
    print(f"Running {len(questions)} questions ({limit_label}) from {questions_path}")

    results: list[dict[str, Any]] = []
    for index, question in enumerate(questions, start=1):
        answer_result = run_answer_question(
            question=question["question"],
            database=args.database,
            collection=args.collection,
            provider=args.provider,
            model=args.model,
            timeout_seconds=args.timeout_seconds,
            verbose=True,
            disable_abstention=args.disable_abstention,
            disable_graph_reasoning=args.disable_graph_reasoning,
        )
        predicted_answer = str(answer_result.get("answer") or "").strip()
        score, judge_reason = judge_answer(
            question=question["question"],
            predicted_answer=predicted_answer,
            gold_answer=question["gold_answer"],
            provider=args.provider,
            model=args.model,
            timeout_seconds=args.timeout_seconds,
        )
        doc_ids = evidence_doc_ids(answer_result)
        result = {
            "question_id": question["question_id"],
            "category": question["category"],
            "question": question["question"],
            "predicted_answer": predicted_answer,
            "gold_answer": question["gold_answer"],
            "retrieved_doc_ids": doc_ids,
            "retrieved_scores": [],
            "ground_truth_doc_ids": question["ground_truth_doc_ids"],
            "score": score,
            "score_value": {"yes": 1.0, "partial": 0.5, "no": 0.0}[score],
            "judge_reason": judge_reason,
            "confidence": answer_result.get("confidence"),
            "abstained": bool(answer_result.get("abstained", False)),
            "evidence_doc_ids": doc_ids,
        }
        results.append(result)
        print(
            f"[{index}/{len(questions)}] {result['question_id']} "
            f"{result['category']} score={score} abstained={result['abstained']}"
        )

    args.results_path.parent.mkdir(parents=True, exist_ok=True)
    args.results_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    summarize(results)
    print_abstention_summary(results, load_baseline_results())
    print()
    print(f"Saved full results to {args.results_path}")


if __name__ == "__main__":
    main()