"""Filter benchmark questions to those answerable from the ingested corpus."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval.baseline import load_questions, resolve_questions_path  # noqa: E402


# Preferred: the filtered batch extraction output. Fallback: batch_extract.py's
# default output, which is the same document list before filtering.
DEFAULT_EXTRACTION_RESULTS_PATHS = (
    PROJECT_ROOT / "eval" / "results" / "batch_extraction_output_filtered.json",
    PROJECT_ROOT / "eval" / "results" / "batch_extraction_output.json",
)
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "eval" / "data" / "questions_answerable.jsonl"


def resolve_extraction_results_path(explicit_path: Path | None) -> Path:
    if explicit_path:
        return explicit_path
    for path in DEFAULT_EXTRACTION_RESULTS_PATHS:
        if path.exists():
            return path
    raise FileNotFoundError(
        "Could not find batch extraction results. Tried: "
        + ", ".join(str(path) for path in DEFAULT_EXTRACTION_RESULTS_PATHS)
    )


def load_ingested_doc_ids(path: Path) -> set[str]:
    """Collect source_doc_ids for documents that were actually ingested."""
    data = json.loads(path.read_text(encoding="utf-8"))
    ingested: set[str] = set()
    for item in data.get("results") or []:
        document = item.get("document") or {}
        source_id = document.get("source_id")
        if source_id:
            ingested.add(str(source_id))
    return ingested


def question_is_answerable(question: dict[str, Any], ingested_doc_ids: set[str]) -> bool:
    return any(
        str(doc_id) in ingested_doc_ids
        for doc_id in (question.get("ground_truth_doc_ids") or [])
    )


def filter_answerable_questions(
    questions_path: Path | None,
    extraction_results_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    resolved_questions_path = resolve_questions_path(questions_path)
    questions = load_questions(resolved_questions_path)
    ingested_doc_ids = load_ingested_doc_ids(extraction_results_path)
    if not ingested_doc_ids:
        raise RuntimeError(f"No ingested documents found in {extraction_results_path}.")

    answerable = [
        question
        for question in questions
        if question_is_answerable(question, ingested_doc_ids)
    ]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        for question in answerable:
            file.write(json.dumps(question["raw"], ensure_ascii=False) + "\n")

    total = len(questions)
    answerable_count = len(answerable)
    return {
        "questions_path": str(resolved_questions_path),
        "extraction_results_path": str(extraction_results_path),
        "total_questions": total,
        "answerable_questions": answerable_count,
        "coverage": answerable_count / total if total else 0.0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Keep only benchmark questions whose ground-truth docs were ingested."
    )
    parser.add_argument("--questions", type=Path, default=None)
    parser.add_argument(
        "--extraction-results",
        type=Path,
        default=None,
        help="Batch extraction output with the ingested document list "
        f"(default: first existing of {', '.join(str(p) for p in DEFAULT_EXTRACTION_RESULTS_PATHS)}).",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    args = parser.parse_args()

    try:
        extraction_results_path = resolve_extraction_results_path(args.extraction_results)
        summary = filter_answerable_questions(
            questions_path=args.questions,
            extraction_results_path=extraction_results_path,
            output_path=args.output,
        )
    except Exception as exc:
        print(f"Filtering failed: {exc}", file=sys.stderr)
        return 1

    total = summary["total_questions"]
    answerable = summary["answerable_questions"]
    coverage = summary["coverage"]
    print(f"Total questions: {total}")
    print(f"Answerable questions: {answerable}")
    print(f"Coverage: {coverage:.1%}")
    print(f"Saved answerable questions to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
