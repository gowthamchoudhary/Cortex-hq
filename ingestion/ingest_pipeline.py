"""Orchestrate source normalization, extraction, graph ingestion, and resolution."""

from __future__ import annotations

import os
from dataclasses import asdict
from pathlib import Path
from typing import Any

from eval.baseline import load_documents, normalize_json_file, normalize_text_file
from extraction.batch_extract import (
    DEFAULT_MAX_CONTENT_CHARS,
    extract_with_backoff,
)
from graph.ingest_to_hydradb import (
    BATCH_SIZE,
    DATABASE_NAME,
    batched,
    build_graph_documents,
    get_api_key,
    ingest_batch,
    update_metadata_schema,
    wait_for_ingestion,
)
from hydra_db import HydraDB
from ingestion.github_fetch import fetch_repo_activity
from ingestion.normalize import (
    normalize_gmail,
    normalize_github,
    normalize_slack,
    parse_gmail_takeout,
    parse_slack_export,
)
from resolution.entity_resolution import run_resolution
from temporal.conflict_cascade import run_cascade
from temporal.truth_discovery import run_truth_discovery


SOURCE_TYPE_TO_ADAPTER = {
    "gmail-export": "gmail",
    "slack-export": "slack",
    "github-repo": "github",
}
# Default access level applied to newly ingested data per uploading role.
# Admin-uploaded company data defaults to "internal" (visible to members);
# "restricted" is only applied when explicitly requested via access_level.
ROLE_TO_ACCESS_LEVEL = {
    "guest": "public",
    "member": "internal",
    "admin": "internal",
}
ACCESS_LEVELS = ("public", "internal", "restricted")
EXTRACTION_TIMEOUT_SECONDS = 60
EXTRACTION_RETRIES = 3
EXTRACTION_BACKOFF_SECONDS = 5.0


def _load_source_documents(source_type: str, source_path_or_repo: str | Path) -> list[Any]:
    if source_type not in SOURCE_TYPE_TO_ADAPTER:
        supported = ", ".join(sorted(SOURCE_TYPE_TO_ADAPTER))
        raise ValueError(f"Unsupported source_type {source_type!r}; choose one of {supported}.")

    if source_type == "github-repo":
        # The "path" for a github-repo source is an owner/name slug, not a file.
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            raise RuntimeError(
                "GITHUB_TOKEN environment variable is required for github-repo ingestion."
            )
        raw_records = fetch_repo_activity(str(source_path_or_repo), token)
        return [normalize_github(record) for record in raw_records]

    source_path = Path(source_path_or_repo)
    if not source_path.exists():
        raise FileNotFoundError(f"Source path does not exist: {source_path}")

    if source_type == "gmail-export":
        return [normalize_gmail(record) for record in parse_gmail_takeout(source_path)]
    if source_type == "slack-export":
        return [normalize_slack(record) for record in parse_slack_export(source_path)]

    # Benchmark-format fallback for plain gmail/slack/github/jira inputs.
    adapter_source = SOURCE_TYPE_TO_ADAPTER[source_type]
    if source_path.is_dir():
        return load_documents([(adapter_source, source_path)])
    if source_path.suffix.lower() in {".json", ".jsonl"}:
        return normalize_json_file(source_path, adapter_source)
    if source_path.suffix.lower() in {".txt", ".md"}:
        return [normalize_text_file(source_path, adapter_source)]
    raise ValueError(
        f"Unsupported source file format {source_path.suffix!r}; "
        "use a JSON/JSONL export, TXT/MD file, or directory."
    )


def _extract_documents(documents: list[Any]) -> tuple[list[dict[str, Any]], int]:
    results: list[dict[str, Any]] = []
    skipped_count = 0
    for document in documents:
        try:
            extraction = extract_with_backoff(
                document=document,
                provider="auto",
                timeout_seconds=EXTRACTION_TIMEOUT_SECONDS,
                max_content_chars=DEFAULT_MAX_CONTENT_CHARS,
                retries=EXTRACTION_RETRIES,
                backoff_seconds=EXTRACTION_BACKOFF_SECONDS,
            )
            results.append({"document": asdict(document), "extraction": extraction})
        except Exception as exc:
            skipped_count += 1
            print(f"Skipped source_id={document.source_id}: {exc}")
    return results, skipped_count


def _ingest_graph(
    extraction_results: list[dict[str, Any]],
    collection: str,
    access_level: str,
) -> dict[str, int]:
    graph_sources, graph_summary = build_graph_documents(
        extraction_results,
        limit=None,
        default_access_level=access_level,
    )
    if not graph_sources:
        return graph_summary

    client = HydraDB(token=get_api_key())
    update_metadata_schema(client, DATABASE_NAME)
    for batch in batched(graph_sources, BATCH_SIZE):
        ids = ingest_batch(client, DATABASE_NAME, collection, batch)
        wait_for_ingestion(client, DATABASE_NAME, collection, ids)
    return graph_summary


def _conflicts_resolved(cascade_summary: dict[str, Any]) -> int:
    return sum(
        int(cascade_summary.get(key, 0))
        for key in (
            "resolved_via_authority",
            "resolved_via_corroboration",
            "resolved_via_recency",
            "resolved_via_last_write_wins",
        )
    )


def run_full_ingestion(
    collection: str,
    source_type: str,
    source_path_or_repo: str | Path,
    role_default: str = "member",
    access_level: str | None = None,
) -> dict[str, int]:
    """Run the complete ingestion pipeline for one source into one collection.

    ``role_default`` selects the default access level for ingested data via
    ``ROLE_TO_ACCESS_LEVEL`` (admin-uploaded data defaults to ``internal``).
    Pass ``access_level`` explicitly to override the role default — use it for
    ``restricted`` data, which is never the automatic default.
    """
    if not str(collection).strip():
        raise ValueError("collection must not be empty.")

    normalized_source_type = source_type.strip().lower()
    if access_level is not None:
        access_level = access_level.strip().lower()
        if access_level not in ACCESS_LEVELS:
            supported = ", ".join(ACCESS_LEVELS)
            raise ValueError(f"Unsupported access_level {access_level!r}; choose one of {supported}.")
    else:
        access_level = ROLE_TO_ACCESS_LEVEL.get(role_default.strip().lower())
        if access_level is None:
            supported = ", ".join(sorted(ROLE_TO_ACCESS_LEVEL))
            raise ValueError(f"Unsupported role_default {role_default!r}; choose one of {supported}.")

    documents = _load_source_documents(normalized_source_type, source_path_or_repo)
    extraction_results, _skipped_count = _extract_documents(documents)
    graph_summary = _ingest_graph(extraction_results, collection, access_level)

    resolution_summary = run_resolution(
        database=DATABASE_NAME,
        collection=collection,
        limit=None,
        dry_run=False,
    )
    run_truth_discovery(
        database=DATABASE_NAME,
        collection=collection,
        dry_run=False,
        iterations=8,
        convergence_delta=0.01,
    )
    cascade_summary = run_cascade(
        database=DATABASE_NAME,
        collection=collection,
        dry_run=False,
        limit_groups=None,
        disabled=False,
        use_learned_authority=True,
    )

    return {
        "docs_processed": len(extraction_results),
        "entities_found": int(graph_summary.get("entities_created", 0)),
        "merges_made": int(resolution_summary.get("auto_merges_made", 0)),
        "conflicts_resolved": _conflicts_resolved(cascade_summary),
    }