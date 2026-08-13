"""Naive Fireflies + Gmail baseline for EnterpriseRAG-Bench questions."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any

import httpx


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ingestion.normalize import ADAPTERS, RawDocument, infer_source_type, load_records


PARTIAL_CORPUS_NOTE = (
    "Baseline run using Fireflies + Gmail only (partial corpus) — scores on "
    "Conflicting Info, Completeness, and categories requiring other sources will "
    "be artificially low until more sources are added."
)

DEFAULT_QUESTIONS_PATHS = (
    PROJECT_ROOT / "eval" / "data" / "questions.jsonl",
    PROJECT_ROOT / "Datasets" / "questions" / "question.jsonl",
)
DEFAULT_FIRE_FLIES_DIR = PROJECT_ROOT / "Datasets" / "fireflies"
DEFAULT_GMAIL_DIR = PROJECT_ROOT / "Datasets" / "gmail"
DEFAULT_RESULTS_PATH = PROJECT_ROOT / "eval" / "results" / "baseline_run.json"
DEFAULT_MODEL = "llama-3.1-8b-instant"
GROQ_CHAT_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
OPENAI_CHAT_ENDPOINT = "https://api.openai.com/v1/chat/completions"
TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_./:-]*", re.IGNORECASE)


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


def resolve_questions_path(explicit_path: Path | None) -> Path:
    if explicit_path:
        return explicit_path
    for path in DEFAULT_QUESTIONS_PATHS:
        if path.exists():
            return path
    raise FileNotFoundError(
        "Could not find questions file. Tried: "
        + ", ".join(str(path) for path in DEFAULT_QUESTIONS_PATHS)
    )


def load_questions(path: Path) -> list[dict[str, Any]]:
    questions: list[dict[str, Any]] = []
    with path.open(encoding="utf-8-sig") as file:
        for line in file:
            if line.strip():
                raw = json.loads(line)
                questions.append(
                    {
                        "question_id": raw.get("question_id") or raw.get("id"),
                        "question": raw.get("question") or raw.get("query") or raw.get("prompt"),
                        "category": raw.get("category") or raw.get("question_type") or "uncategorized",
                        "gold_answer": raw.get("gold_answer")
                        or raw.get("answer")
                        or raw.get("expected_answer"),
                        "ground_truth_doc_ids": raw.get("expected_doc_ids")
                        or raw.get("ground_truth_doc_ids")
                        or raw.get("doc_ids")
                        or raw.get("references")
                        or [],
                        "source_types": raw.get("source_types") or [],
                        "raw": raw,
                    }
                )
    return questions


def source_id_from_path(path: Path) -> str:
    return path.stem.split("__", 1)[0]


def timestamp_from_path_or_text(path: Path, text: str) -> str:
    match = re.search(r"__(\d{4})-?(\d{2})-?(\d{2})", path.stem)
    if match:
        return "-".join(match.groups())
    match = re.search(r"(?:Date|First email at|Created):\s*([^\n\r]+)", text, re.IGNORECASE)
    return match.group(1).strip() if match else ""


def normalize_text_file(path: Path, source: str) -> RawDocument:
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    source_id = source_id_from_path(path)
    timestamp = timestamp_from_path_or_text(path, text)
    title = text.splitlines()[0].strip() if text.splitlines() else path.stem
    return RawDocument(
        source=source,
        source_id=source_id,
        author="",
        timestamp=timestamp,
        content=text,
        container_id=path.parent.name,
        metadata={"path": str(path), "title": title},
    )


def normalize_json_file(path: Path, source: str) -> list[RawDocument]:
    records = load_records(path)
    if not records:
        return []

    first = records[0]
    if {"source", "source_id", "content", "container_id"}.issubset(first):
        return [
            RawDocument(
                source=str(record.get("source", source)),
                source_id=str(record.get("source_id", "")),
                author=str(record.get("author", "")),
                timestamp=str(record.get("timestamp", "")),
                content=str(record.get("content", "")),
                container_id=str(record.get("container_id", "")),
                metadata=dict(record.get("metadata") or {}),
            )
            for record in records
        ]

    source_type = source if source in ADAPTERS else infer_source_type(path, first)
    adapter = ADAPTERS[source_type]
    return [adapter(record) for record in records]


def load_documents(source_dirs: list[tuple[str, Path]]) -> list[RawDocument]:
    documents: list[RawDocument] = []
    for source, source_dir in source_dirs:
        if not source_dir.exists():
            continue
        for path in sorted(item for item in source_dir.rglob("*") if item.is_file()):
            suffix = path.suffix.lower()
            if suffix in {".json", ".jsonl"}:
                documents.extend(normalize_json_file(path, source))
            elif suffix in {".txt", ".md"}:
                documents.append(normalize_text_file(path, source))
    return documents


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text)]


def build_doc_frequencies(documents: list[RawDocument]) -> Counter[str]:
    frequencies: Counter[str] = Counter()
    for document in documents:
        frequencies.update(set(tokenize(document.content)))
    return frequencies


def retrieve(
    question: str,
    documents: list[RawDocument],
    doc_frequencies: Counter[str],
    top_k: int,
) -> list[tuple[RawDocument, float]]:
    query_terms = Counter(tokenize(question))
    if not query_terms:
        return []

    scored: list[tuple[RawDocument, float]] = []
    doc_count = len(documents)
    for document in documents:
        doc_terms = Counter(tokenize(document.content))
        if not doc_terms:
            continue
        score = 0.0
        for term, query_count in query_terms.items():
            if term not in doc_terms:
                continue
            idf = math.log((doc_count + 1) / (doc_frequencies[term] + 1)) + 1
            score += query_count * (1 + math.log(doc_terms[term])) * idf
        if score:
            scored.append((document, score))

    return sorted(scored, key=lambda item: item[1], reverse=True)[:top_k]


def provider_config(provider: str, model: str | None) -> tuple[str, str, str]:
    if provider == "auto":
        provider = "groq" if os.environ.get("GROQ_API_KEY") else "openai"

    if provider == "groq":
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY is required for Groq baseline runs.")
        return GROQ_CHAT_ENDPOINT, api_key, model or os.environ.get("GROQ_MODEL", DEFAULT_MODEL)

    if provider == "openai":
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required for OpenAI baseline runs.")
        return OPENAI_CHAT_ENDPOINT, api_key, model or os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")

    raise ValueError(f"Unsupported provider: {provider}")


def call_llm_json(
    messages: list[dict[str, str]],
    provider: str,
    model: str | None,
    timeout_seconds: int,
    retries: int = 2,
) -> dict[str, Any]:
    endpoint, api_key, resolved_model = provider_config(provider, model)
    body = {
        "model": resolved_model,
        "messages": messages,
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }

    try:
        response = httpx.post(
            endpoint,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "cortex-hydradb-baseline/0.1",
            },
            json=body,
            timeout=timeout_seconds,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 429 and retries > 0:
            time.sleep(4)
            return call_llm_json(messages, provider, model, timeout_seconds, retries - 1)
        raise RuntimeError(
            f"LLM API returned HTTP {exc.response.status_code}: {exc.response.text}"
        ) from exc

    content = response.json()["choices"][0]["message"]["content"]
    return json.loads(content)


def answer_question(
    question: str,
    retrieved_docs: list[tuple[RawDocument, float]],
    provider: str,
    model: str | None,
    timeout_seconds: int,
    max_doc_chars: int,
) -> str:
    context_blocks = []
    for rank, (document, score) in enumerate(retrieved_docs, start=1):
        context_blocks.append(
            "\n".join(
                [
                    f"[{rank}] source_id={document.source_id} source={document.source} score={score:.3f}",
                    document.content[:max_doc_chars],
                ]
            )
        )

    messages = [
        {
            "role": "system",
            "content": (
                "Answer the user's question using only the provided context. "
                "If the context does not support an answer, return not found. "
                "Return JSON exactly like {\"answer\": \"...\"}."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {"question": question, "context": "\n\n---\n\n".join(context_blocks)}
            ),
        },
    ]
    result = call_llm_json(messages, provider, model, timeout_seconds)
    return str(result.get("answer", "not found")).strip() or "not found"


def judge_answer(
    question: str,
    predicted_answer: str,
    gold_answer: str,
    provider: str,
    model: str | None,
    timeout_seconds: int,
) -> tuple[str, str]:
    messages = [
        {
            "role": "system",
            "content": (
                "Judge whether the predicted answer matches the gold answer in meaning "
                "for the question. Return JSON exactly like "
                "{\"score\": \"yes|partial|no\", \"reason\": \"brief reason\"}."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "question": question,
                    "gold_answer": gold_answer,
                    "predicted_answer": predicted_answer,
                }
            ),
        },
    ]
    result = call_llm_json(messages, provider, model, timeout_seconds)
    score = str(result.get("score", "no")).lower().strip()
    if score not in {"yes", "partial", "no"}:
        score = "no"
    return score, str(result.get("reason", "")).strip()


def summarize(results: list[dict[str, Any]]) -> None:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for result in results:
        grouped[result["category"]].append(result)

    print(PARTIAL_CORPUS_NOTE)
    print()
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a naive Fireflies + Gmail RAG baseline.")
    parser.add_argument("--questions", type=Path, default=None)
    parser.add_argument("--fireflies-dir", type=Path, default=DEFAULT_FIRE_FLIES_DIR)
    parser.add_argument("--gmail-dir", type=Path, default=DEFAULT_GMAIL_DIR)
    parser.add_argument("--results-path", type=Path, default=DEFAULT_RESULTS_PATH)
    parser.add_argument("--provider", choices=("auto", "groq", "openai"), default="auto")
    parser.add_argument("--model", default=None)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--limit", type=int, default=None, help="Optional question limit for smoke tests.")
    parser.add_argument("--max-doc-chars", type=int, default=1500)
    parser.add_argument("--timeout-seconds", type=int, default=90)
    args = parser.parse_args()

    load_dotenv()
    questions_path = resolve_questions_path(args.questions)
    questions = load_questions(questions_path)
    if args.limit is not None:
        questions = questions[: args.limit]

    documents = load_documents(
        [
            ("fireflies", args.fireflies_dir),
            ("gmail", args.gmail_dir),
        ]
    )
    if not documents:
        raise RuntimeError("No Fireflies or Gmail documents were loaded.")

    doc_frequencies = build_doc_frequencies(documents)
    results: list[dict[str, Any]] = []
    for index, question in enumerate(questions, start=1):
        retrieved = retrieve(question["question"], documents, doc_frequencies, args.top_k)
        predicted_answer = answer_question(
            question=question["question"],
            retrieved_docs=retrieved,
            provider=args.provider,
            model=args.model,
            timeout_seconds=args.timeout_seconds,
            max_doc_chars=args.max_doc_chars,
        )
        score, judge_reason = judge_answer(
            question=question["question"],
            predicted_answer=predicted_answer,
            gold_answer=question["gold_answer"],
            provider=args.provider,
            model=args.model,
            timeout_seconds=args.timeout_seconds,
        )

        result = {
            "question_id": question["question_id"],
            "category": question["category"],
            "question": question["question"],
            "predicted_answer": predicted_answer,
            "gold_answer": question["gold_answer"],
            "retrieved_doc_ids": [document.source_id for document, _ in retrieved],
            "retrieved_scores": [score for _, score in retrieved],
            "ground_truth_doc_ids": question["ground_truth_doc_ids"],
            "score": score,
            "score_value": {"yes": 1.0, "partial": 0.5, "no": 0.0}[score],
            "judge_reason": judge_reason,
        }
        results.append(result)
        print(
            f"[{index}/{len(questions)}] {result['question_id']} "
            f"{result['category']} score={score}"
        )

    args.results_path.parent.mkdir(parents=True, exist_ok=True)
    args.results_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    summarize(results)
    print()
    print(f"Saved full results to {args.results_path}")


if __name__ == "__main__":
    main()
