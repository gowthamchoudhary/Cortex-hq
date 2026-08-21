"""Orchestrate source normalization, extraction, graph ingestion, and resolution."""

from __future__ import annotations

import gc
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
from ingestion.github_fetch import clean_repo_slug, fetch_repo_activity
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
    "gmail-live": "gmail",
    "slack-export": "slack",
    "slack-live": "slack",
    "github-repo": "github",
}
# Source types that use live OAuth tokens instead of file uploads.
LIVE_OAUTH_TYPES = {"gmail-live", "slack-live"}
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
EXTRACTION_BATCH_SIZE = 10  # documents per batch to limit peak memory


def _load_source_documents(source_type: str, source_path_or_repo: str | Path, collection: str = "") -> list[Any]:
    if source_type not in SOURCE_TYPE_TO_ADAPTER:
        supported = ", ".join(sorted(SOURCE_TYPE_TO_ADAPTER))
        raise ValueError(f"Unsupported source_type {source_type!r}; choose one of {supported}.")

    # Live OAuth sources: fetch messages via API instead of file upload.
    if source_type == "gmail-live":
        from oauth.tokens import get_token
        token_data = get_token(collection, "gmail")
        if not token_data or not token_data.get("access_token"):
            raise RuntimeError("Gmail OAuth token not found. Connect Gmail first via the Sources page.")
        from ingestion.gmail_fetch import fetch_gmail_messages
        raw_records = fetch_gmail_messages(token_data["access_token"])
        return [normalize_gmail(record) for record in raw_records]

    if source_type == "slack-live":
        from oauth.tokens import get_token
        token_data = get_token(collection, "slack")
        if not token_data or not token_data.get("access_token"):
            raise RuntimeError("Slack OAuth token not found. Connect Slack first via the Sources page.")
        from ingestion.slack_fetch import fetch_slack_messages
        raw_records = fetch_slack_messages(token_data["access_token"])
        return [normalize_slack(record) for record in raw_records]

    if source_type == "github-repo":
        # The "path" for a github-repo source is an owner/name slug, not a file.
        # Try per-collection OAuth token first; fall back to global GITHUB_TOKEN.
        token = ""
        if collection:
            try:
                from oauth.tokens import get_token
                token_data = get_token(collection, "github")
                if token_data and token_data.get("access_token"):
                    token = token_data["access_token"]
            except Exception:  # noqa: BLE001
                pass
        if not token:
            token = os.environ.get("GITHUB_TOKEN")
        if not token:
            raise RuntimeError(
                "No GitHub token found. Connect GitHub via OAuth in the Sources page, "
                "or set the GITHUB_TOKEN environment variable."
            )
        cleaned_repo = clean_repo_slug(str(source_path_or_repo))
        raw_records = fetch_repo_activity(cleaned_repo, token)
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


def _extract_documents(documents: list[Any]) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    results: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    total = len(documents)
    print(f"[EXTRACT] Starting extraction of {total} documents")
    for batch_start in range(0, total, EXTRACTION_BATCH_SIZE):
        batch = documents[batch_start:batch_start + EXTRACTION_BATCH_SIZE]
        for document in batch:
            try:
                extraction = extract_with_backoff(
                    document=document,
                    provider="auto",
                    timeout_seconds=EXTRACTION_TIMEOUT_SECONDS,
                    max_content_chars=DEFAULT_MAX_CONTENT_CHARS,
                    retries=EXTRACTION_RETRIES,
                    backoff_seconds=EXTRACTION_BACKOFF_SECONDS,
                )
                entities = len(extraction.get("candidate_entities", []))
                facts = len(extraction.get("candidate_facts", []))
                relations = len(extraction.get("candidate_relations", []))
                print(
                    f"[EXTRACT] source_id={document.source_id} "
                    f"→ {entities} entities, {facts} facts, {relations} relations"
                )
                results.append({"document": asdict(document), "extraction": extraction})
            except Exception as exc:
                skipped.append({
                    "source_id": document.source_id,
                    "error": str(exc),
                })
                print(f"[EXTRACT] SKIPPED source_id={document.source_id}: {exc}")
        del batch
        gc.collect()
    print(f"[EXTRACT] Done: {len(results)} extracted, {len(skipped)} skipped")
    return results, skipped


def _ingest_graph(
    extraction_results: list[dict[str, Any]],
    collection: str,
    access_level: str,
) -> dict[str, int]:
    print(f"[INGEST] Building graph documents from {len(extraction_results)} extractions")
    graph_sources, graph_summary = build_graph_documents(
        extraction_results,
        limit=None,
        default_access_level=access_level,
    )
    print(
        f"[INGEST] Graph documents built: {len(graph_sources)} sources, "
        f"{graph_summary.get('entities_created', 0)} entities, "
        f"{graph_summary.get('facts_created', 0)} facts, "
        f"{graph_summary.get('relations_created', 0)} relations, "
        f"{graph_summary.get('failures', 0)} failures"
    )
    if not graph_sources:
        print("[INGEST] WARNING: No graph sources to ingest — extraction may have produced empty results or all docs were skipped")
        return graph_summary

    print(f"[INGEST] Target collection={collection!r}, database={DATABASE_NAME!r}")
    client = HydraDB(token=get_api_key())
    update_metadata_schema(client, DATABASE_NAME)
    batch_num = 0
    for batch in batched(graph_sources, BATCH_SIZE):
        batch_num += 1
        print(f"[INGEST] Ingesting batch {batch_num} with {len(batch)} records into collection {collection!r}...")
        ids = ingest_batch(client, DATABASE_NAME, collection, batch)
        print(f"[INGEST] Batch {batch_num} submitted, waiting for ingestion of {len(ids)} records...")
        statuses = wait_for_ingestion(client, DATABASE_NAME, collection, ids)
        completed = sum(1 for s in statuses if s.get("indexing_status") == "completed")
        errored = sum(1 for s in statuses if s.get("indexing_status") == "errored")
        print(f"[INGEST] Batch {batch_num} done: {completed} completed, {errored} errored")
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

    print(f"[PIPELINE] Starting ingestion: collection={collection!r}, source_type={normalized_source_type!r}")
    documents = _load_source_documents(normalized_source_type, source_path_or_repo, collection=collection)
    print(f"[PIPELINE] Loaded {len(documents)} source documents")
    extraction_results, skipped_docs = _extract_documents(documents)
    # Release source documents now that extraction is done.
    del documents
    gc.collect()

    if not extraction_results:
        error_messages = [entry["error"] for entry in skipped_docs[:3]]
        detail = "; ".join(error_messages) if error_messages else "unknown error"
        raise RuntimeError(
            f"Extraction failed: all documents were skipped — {detail}"
        )

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
        "docs_skipped": len(skipped_docs),
        "entities_found": int(graph_summary.get("entities_created", 0)),
        "merges_made": int(resolution_summary.get("auto_merges_made", 0)),
        "conflicts_resolved": _conflicts_resolved(cascade_summary),
    }