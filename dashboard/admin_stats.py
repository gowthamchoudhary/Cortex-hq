"""Read-only aggregations for the administrator dashboard."""

from __future__ import annotations

import os
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from hydra_db import HydraDB


DATABASE_NAME = os.environ.get("HYDRADB_DATABASE", "hackhydra-track1")
PAGE_SIZE = 100


def _to_plain_data(value: Any) -> Any:
    """Convert HydraDB response models into ordinary Python data."""
    if hasattr(value, "model_dump"):
        return _to_plain_data(value.model_dump())
    if hasattr(value, "dict"):
        return _to_plain_data(value.dict())
    if isinstance(value, dict):
        return {key: _to_plain_data(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_plain_data(item) for item in value]
    if hasattr(value, "__dict__"):
        return _to_plain_data(vars(value))
    return value


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _record_metadata(record: dict[str, Any]) -> dict[str, Any]:
    """Merge record-level and nested metadata without mutating the response."""
    metadata = _mapping(record.get("metadata"))
    additional_metadata = _mapping(record.get("additional_metadata"))
    merged = dict(additional_metadata)
    merged.update(metadata)
    return merged


def _record_type(record: dict[str, Any]) -> str:
    metadata = _record_metadata(record)
    return str(
        metadata.get("record_type")
        or metadata.get("type")
        or record.get("record_type")
        or record.get("type")
        or record.get("kind")
        or ""
    ).strip().casefold()


def _record_value(record: dict[str, Any], key: str) -> Any:
    metadata = _record_metadata(record)
    return metadata.get(key, record.get(key))


def _timestamp_sort_key(value: Any) -> tuple[int, Any]:
    """Return a comparable key for Unix timestamps and ISO date strings."""
    if value is None or value == "":
        return (-1, "")

    if isinstance(value, (int, float)):
        return (1, float(value))

    text = str(value).strip()
    try:
        return (1, float(text))
    except ValueError:
        pass

    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return (1, parsed.timestamp())
    except ValueError:
        # Keep an unrecognised non-empty value deterministic without making
        # the entire dashboard fail because one source has malformed data.
        return (0, text)


def _api_key() -> str:
    api_key = os.environ.get("HYDRADB_API_KEY")
    if not api_key:
        raise RuntimeError("HYDRADB_API_KEY environment variable is required.")
    return api_key


def _list_sources(client: HydraDB, collection: str) -> list[dict[str, Any]]:
    """Read every knowledge source in a collection, following pagination."""
    sources: list[dict[str, Any]] = []
    page = 1

    while True:
        response = client.context.list(
            database=DATABASE_NAME,
            collection=collection,
            type="knowledge",
            page=page,
            page_size=PAGE_SIZE,
        )
        data = _to_plain_data(response.data)
        if not isinstance(data, dict):
            raise TypeError("HydraDB context.list returned an unexpected response shape.")

        sources.extend(
            source for source in (data.get("sources") or []) if isinstance(source, dict)
        )
        pagination = _mapping(data.get("pagination"))
        if not pagination.get("has_next"):
            break
        page += 1

    return sources


def get_admin_dashboard_data(collection: str) -> dict[str, Any]:
    """Return aggregate counts and ingestion metadata for ``collection``.

    The function only calls HydraDB's context listing endpoint; it does not
    create, update, or delete any records. ``collection`` is the HydraDB
    collection name used with the project's default database.
    """
    if not str(collection).strip():
        raise ValueError("collection must not be empty.")

    client = HydraDB(token=_api_key())
    records = _list_sources(client, str(collection))

    counts = Counter(_record_type(record) for record in records)
    source_types: Counter[str] = Counter()
    latest_timestamp: Any = None
    latest_key: tuple[int, Any] = (0, 0)

    for record in records:
        record_type = _record_type(record)
        if record_type == "document":
            source_type = _record_value(record, "doc_source_type")
            if source_type not in (None, ""):
                source_types[str(source_type)] += 1

        # Prefer created_at when present, then txn_from as requested by the
        # ingestion schema. Values are returned unchanged for UI formatting.
        timestamp = _record_value(record, "created_at")
        if timestamp in (None, ""):
            timestamp = _record_value(record, "txn_from")
        timestamp_key = _timestamp_sort_key(timestamp)
        if timestamp_key > latest_key:
            latest_key = timestamp_key
            latest_timestamp = timestamp

    pending_merges = sum(
        1
        for record in records
        if _record_type(record) == "candidatemerge"
        and str(_record_value(record, "state") or "").strip().casefold() == "pending"
    )
    disputed_facts = sum(
        1
        for record in records
        if _record_type(record) == "factstate"
        and str(_record_value(record, "state") or "").strip().casefold() == "disputed"
    )

    return {
        "total_documents": counts["document"],
        "total_entities": counts["entity"],
        "total_facts": counts["factstate"],
        "total_relations": counts["relation"],
        "pending_merges": pending_merges,
        "disputed_facts": disputed_facts,
        "last_ingestion_timestamp": latest_timestamp,
        "source_type_breakdown": dict(source_types),
    }