"""Fit an abstention confidence calibration from judged QA results."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.linear_model import LogisticRegression


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval.baseline import judge_answer, load_dotenv, load_questions, resolve_questions_path  # noqa: E402
from reasoning.answer_question import DATABASE_NAME, answer_question  # noqa: E402


DEFAULT_LIMIT = 40
DEFAULT_OUTPUT = PROJECT_ROOT / "reasoning" / "calibration.json"


def logit(probability: float) -> float:
    probability = max(1e-6, min(1 - 1e-6, probability))
    return math.log(probability / (1 - probability))


def probability(coefficient: float, intercept: float, confidence: float) -> float:
    z_value = coefficient * confidence + intercept
    return 1 / (1 + math.exp(-z_value))


def threshold_for_target(coefficient: float, intercept: float, target_probability: float) -> float:
    if abs(coefficient) < 1e-9:
        return 1.0
    if coefficient < 0:
        return 0.0 if probability(coefficient, intercept, 0.0) >= target_probability else 1.0
    threshold = (logit(target_probability) - intercept) / coefficient
    return max(0.0, min(1.0, threshold))


def fit_calibration(confidences: list[float], labels: list[int], target_probability: float) -> dict[str, Any]:
    label_values = set(labels)
    if len(label_values) < 2:
        rate = sum(labels) / len(labels) if labels else 0.0
        intercept = logit(rate) if 0 < rate < 1 else (10.0 if rate >= 1 else -10.0)
        return {
            "model": "constant",
            "coefficient": 0.0,
            "intercept": intercept,
            "observed_accuracy": rate,
            "recommended_threshold": 0.0 if rate >= target_probability else 1.0,
            "note": "Only one correctness class observed; saved a constant calibration.",
        }

    x_values = np.array(confidences, dtype=float).reshape(-1, 1)
    y_values = np.array(labels, dtype=int)
    model = LogisticRegression()
    model.fit(x_values, y_values)
    coefficient = float(model.coef_[0][0])
    intercept = float(model.intercept_[0])
    threshold = threshold_for_target(coefficient, intercept, target_probability)
    return {
        "model": "sklearn.linear_model.LogisticRegression",
        "coefficient": coefficient,
        "intercept": intercept,
        "observed_accuracy": float(sum(labels) / len(labels)),
        "recommended_threshold": threshold,
    }


def run_calibration(
    questions_path: Path | None,
    limit: int,
    database: str,
    collection: str,
    provider: str,
    model: str | None,
    timeout_seconds: int,
    target_probability: float,
    output: Path,
) -> dict[str, Any]:
    load_dotenv()
    resolved_questions_path = resolve_questions_path(questions_path)
    questions = [
        question
        for question in load_questions(resolved_questions_path)
        if question.get("question") and question.get("gold_answer")
    ][:limit]
    if not questions:
        raise RuntimeError("No questions with gold answers were found.")

    samples: list[dict[str, Any]] = []
    confidences: list[float] = []
    labels: list[int] = []

    for index, question in enumerate(questions, start=1):
        qa_result = answer_question(
            question=question["question"],
            database=database,
            collection=collection,
            provider=provider,
            model=model,
            timeout_seconds=timeout_seconds,
            verbose=False,
            disable_abstention=True,
        )
        predicted_answer = str(qa_result.get("answer") or "")
        confidence = float(qa_result.get("confidence") or 0.0)
        judge_score, judge_reason = judge_answer(
            question=question["question"],
            predicted_answer=predicted_answer,
            gold_answer=str(question["gold_answer"]),
            provider=provider,
            model=model,
            timeout_seconds=timeout_seconds,
        )
        correct = 1 if judge_score == "yes" else 0
        confidences.append(confidence)
        labels.append(correct)
        samples.append(
            {
                "question_id": question["question_id"],
                "category": question["category"],
                "question": question["question"],
                "gold_answer": question["gold_answer"],
                "predicted_answer": predicted_answer,
                "raw_confidence": confidence,
                "judge_score": judge_score,
                "correct_label": correct,
                "judge_reason": judge_reason,
            }
        )
        print(
            f"[{index}/{len(questions)}] {question['question_id']} "
            f"confidence={confidence:.3f} judge={judge_score}"
        )

    calibration = fit_calibration(confidences, labels, target_probability)
    calibration.update(
        {
            "target_probability": target_probability,
            "questions_path": str(resolved_questions_path),
            "sample_count": len(samples),
            "samples": samples,
        }
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(calibration, indent=2), encoding="utf-8")
    return calibration


def main() -> int:
    parser = argparse.ArgumentParser(description="Calibrate the reasoning abstention threshold.")
    parser.add_argument("--questions", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--database", default=DATABASE_NAME)
    parser.add_argument("--collection", default="default")
    parser.add_argument("--provider", choices=("auto", "groq", "openai"), default="auto")
    parser.add_argument("--model", default=None)
    parser.add_argument("--timeout-seconds", type=int, default=90)
    parser.add_argument("--target-probability", type=float, default=0.6)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    try:
        if not 0 < args.target_probability < 1:
            raise ValueError("--target-probability must be between 0 and 1.")
        calibration = run_calibration(
            questions_path=args.questions,
            limit=args.limit,
            database=args.database,
            collection=args.collection,
            provider=args.provider,
            model=args.model,
            timeout_seconds=args.timeout_seconds,
            target_probability=args.target_probability,
            output=args.output,
        )
        print("Calibration complete.")
        print(f"- model: {calibration['model']}")
        print(f"- coefficient: {calibration['coefficient']:.6f}")
        print(f"- intercept: {calibration['intercept']:.6f}")
        print(f"- observed accuracy: {calibration['observed_accuracy']:.3f}")
        print(f"- target probability: {calibration['target_probability']:.3f}")
        print(f"- recommended threshold: {calibration['recommended_threshold']:.3f}")
        print(f"- saved to: {args.output}")
        return 0
    except Exception as exc:
        print(f"Calibration failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
