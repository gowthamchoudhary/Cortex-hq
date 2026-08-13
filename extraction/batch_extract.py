"""Batch extraction over normalized source documents."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import httpx


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval.baseline import load_documents  # noqa: E402
from extraction.extract import (  # noqa: E402
    DEFAULT_MAX_CONTENT_CHARS,
    extract_from_document,
    list_groq_models,
    load_dotenv,
)
from ingestion.normalize import RawDocument  # noqa: E402


DEFAULT_DATASETS_ROOT = PROJECT_ROOT / "Datasets"
DEFAULT_OUTPUT = PROJECT_ROOT / "eval" / "results" / "batch_extraction_output.json"
DEFAULT_SOURCES = ("fireflies", "gmail", "github")


def source_dirs(sources: list[str], datasets_root: Path) -> list[tuple[str, Path]]:
    dirs = []
    for source in sources:
        source = source.strip().lower()
        if source:
            dirs.append((source, datasets_root / source))
    return dirs


def normalize_all_documents(sources: list[str], datasets_root: Path, limit: int | None) -> list[RawDocument]:
    documents = load_documents(source_dirs(sources, datasets_root))
    if limit is not None:
        return documents[:limit]
    return documents


def is_rate_limit_error(exc: Exception) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code == 429
    message = str(exc).lower()
    return "429" in message or "rate limit" in message or "too many requests" in message


def extract_with_backoff(
    document: RawDocument,
    provider: str,
    timeout_seconds: int,
    max_content_chars: int,
    retries: int,
    backoff_seconds: float,
) -> dict[str, Any]:
    attempt = 0
    while True:
        try:
            return extract_from_document(
                document,
                provider=provider,
                timeout_seconds=timeout_seconds,
                max_content_chars=max_content_chars,
            )
        except Exception as exc:
            if attempt >= retries or not is_rate_limit_error(exc):
                raise
            sleep_for = backoff_seconds * (2**attempt)
            print(
                f"Rate limited on source_id={document.source_id}; "
                f"retrying in {sleep_for:.1f}s..."
            )
            time.sleep(sleep_for)
            attempt += 1


def count_items(results: list[dict[str, Any]], key: str) -> int:
    return sum(len(result.get("extraction", {}).get(key) or []) for result in results)


def save_output(
    output: Path,
    results: list[dict[str, Any]],
    skipped: list[dict[str, str]],
    sources: list[str],
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "results": results,
        "skipped": skipped,
        "summary": {
            "sources": sources,
            "docs_processed": len(results),
            "docs_skipped": len(skipped),
            "total_entities": count_items(results, "candidate_entities"),
            "total_facts": count_items(results, "candidate_facts"),
            "total_relations": count_items(results, "candidate_relations"),
        },
    }
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def run_batch(
    sources: list[str],
    datasets_root: Path,
    output: Path,
    provider: str,
    limit: int | None,
    timeout_seconds: int,
    max_content_chars: int,
    retries: int,
    backoff_seconds: float,
    progress_every: int,
) -> dict[str, Any]:
    documents = normalize_all_documents(sources, datasets_root, limit)
    if not documents:
        raise RuntimeError(f"No documents found for sources={sources} under {datasets_root}.")

    results: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    started = time.time()

    for index, document in enumerate(documents, start=1):
        try:
            extraction = extract_with_backoff(
                document=document,
                provider=provider,
                timeout_seconds=timeout_seconds,
                max_content_chars=max_content_chars,
                retries=retries,
                backoff_seconds=backoff_seconds,
            )
            results.append({"document": asdict(document), "extraction": extraction})
        except Exception as exc:
            skipped.append(
                {
                    "source": document.source,
                    "source_id": document.source_id,
                    "error": str(exc),
                }
            )
            print(f"Skipped source_id={document.source_id}: {exc}")

        if index % progress_every == 0:
            print(
                f"Progress: {index}/{len(documents)} docs seen, "
                f"{len(results)} processed, {len(skipped)} skipped, "
                f"entities={count_items(results, 'candidate_entities')}, "
                f"facts={count_items(results, 'candidate_facts')}, "
                f"relations={count_items(results, 'candidate_relations')}"
            )

    save_output(output, results, skipped, sources)
    return {
        "docs_seen": len(documents),
        "docs_processed": len(results),
        "docs_skipped": len(skipped),
        "total_entities": count_items(results, "candidate_entities"),
        "total_facts": count_items(results, "candidate_facts"),
        "total_relations": count_items(results, "candidate_relations"),
        "output": str(output),
        "elapsed_seconds": round(time.time() - started, 2),
    }


def parse_sources(value: str) -> list[str]:
    return [source.strip().lower() for source in value.split(",") if source.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch extract graph candidates from source folders.")
    parser.add_argument(
        "--sources",
        default=",".join(DEFAULT_SOURCES),
        help="Comma-separated sources under Datasets/, e.g. fireflies,gmail,github.",
    )
    parser.add_argument("--datasets-root", type=Path, default=DEFAULT_DATASETS_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--provider", choices=("auto", "groq", "openai"), default="auto")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--timeout-seconds", type=int, default=60)
    parser.add_argument("--max-content-chars", type=int, default=DEFAULT_MAX_CONTENT_CHARS)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--backoff-seconds", type=float, default=5.0)
    parser.add_argument("--progress-every", type=int, default=20)
    parser.add_argument("--groq-model", default=None)
    parser.add_argument("--list-groq-models", action="store_true")
    args = parser.parse_args()

    try:
        load_dotenv(PROJECT_ROOT / ".env")
        if args.groq_model:
            os.environ["GROQ_MODEL"] = args.groq_model
        if args.list_groq_models:
            print(json.dumps(list_groq_models(args.timeout_seconds), indent=2))
            return 0

        sources = parse_sources(args.sources)
        summary = run_batch(
            sources=sources,
            datasets_root=args.datasets_root,
            output=args.output,
            provider=args.provider,
            limit=args.limit,
            timeout_seconds=args.timeout_seconds,
            max_content_chars=args.max_content_chars,
            retries=args.retries,
            backoff_seconds=args.backoff_seconds,
            progress_every=max(args.progress_every, 1),
        )
        print("Batch extraction summary:")
        print(f"- docs seen: {summary['docs_seen']}")
        print(f"- docs processed: {summary['docs_processed']}")
        print(f"- docs skipped: {summary['docs_skipped']}")
        print(f"- total entities extracted: {summary['total_entities']}")
        print(f"- total facts extracted: {summary['total_facts']}")
        print(f"- total relations extracted: {summary['total_relations']}")
        print(f"- elapsed seconds: {summary['elapsed_seconds']}")
        print(f"- output: {summary['output']}")
        return 0
    except Exception as exc:
        print(f"Batch extraction failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
