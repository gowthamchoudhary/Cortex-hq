"""Create and inspect organization-specific HydraDB knowledge graph collections."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from hydra_db import HydraDB

from schema.create_collection import (
    DATABASE_NAME,
    collection_names,
    ensure_collection,
    get_api_key,
    to_plain_data,
)


COLLECTION_NAME_MAX_LENGTH = 80
COLLECTION_INIT_MARKER_ID = "__collection_init__"


def slugify(value: str) -> str:
    """Return a safe, deterministic collection-name slug for an organization."""
    normalized = unicodedata.normalize("NFKD", str(value))
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name).strip("-")
    return slug[:COLLECTION_NAME_MAX_LENGTH].rstrip("-") or "brain"


def _unique_collection_name(org_name: str, existing_names: set[str]) -> str:
    base_name = slugify(org_name)
    existing_lower = {name.casefold() for name in existing_names}
    if base_name.casefold() not in existing_lower:
        return base_name

    suffix = 2
    while f"{base_name}-{suffix}".casefold() in existing_lower:
        suffix += 1
    return f"{base_name}-{suffix}"


def _client() -> HydraDB:
    return HydraDB(token=get_api_key())


def _source_metadata(source: dict[str, Any]) -> dict[str, Any]:
    return dict(source.get("metadata") or {})


def _source_additional_metadata(source: dict[str, Any]) -> dict[str, Any]:
    return dict(source.get("additional_metadata") or {})


def _source_type(source: dict[str, Any]) -> str:
    metadata = _source_metadata(source)
    return str(metadata.get("type") or metadata.get("record_type") or source.get("type") or "").casefold()


def _is_collection_marker(source: dict[str, Any]) -> bool:
    if source.get("id") == COLLECTION_INIT_MARKER_ID:
        return True
    return bool(_source_additional_metadata(source).get("system_marker"))


def _source_doc_ids(source: dict[str, Any]) -> set[str]:
    metadata = _source_metadata(source)
    extra = _source_additional_metadata(source)
    value = metadata.get("source_doc_id") or extra.get("source_doc_id")
    if not value:
        return set()
    return {part.strip() for part in str(value).split("|") if part.strip()}


def _list_all_sources(client: HydraDB, collection_name: str) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    page = 1
    while True:
        response = client.context.list(
            database=DATABASE_NAME,
            collection=collection_name,
            type="knowledge",
            page=page,
            page_size=100,
        )
        data = to_plain_data(response.data)
        sources.extend(data.get("sources") or [])
        pagination = data.get("pagination") or {}
        if not pagination.get("has_next"):
            break
        page += 1
    return sources


def create_brain(org_name: str) -> dict[str, str]:
    """Create a unique HydraDB collection for an organization.

    The returned collection name is safe to persist and use in later pipeline
    calls. Existing collections are never overwritten.
    """
    if not str(org_name).strip():
        raise ValueError("org_name must not be empty.")

    client = _client()
    collection_name = _unique_collection_name(org_name, collection_names(client, DATABASE_NAME))
    ensure_collection(client, DATABASE_NAME, collection_name)
    return {"collection_name": collection_name, "status": "ready"}


def get_brain_status(collection_name: str) -> dict[str, int | str]:
    """Return collection readiness and document, entity, and fact counts."""
    if not str(collection_name).strip():
        raise ValueError("collection_name must not be empty.")

    client = _client()
    existing_names = collection_names(client, DATABASE_NAME)
    sources = _list_all_sources(client, collection_name)
    non_marker_sources = [source for source in sources if not _is_collection_marker(source)]

    document_ids: set[str] = set()
    for source in non_marker_sources:
        document_ids.update(_source_doc_ids(source))
        if _source_type(source) == "document" and not _source_doc_ids(source):
            document_ids.add(str(source.get("id") or ""))
    document_ids.discard("")

    entity_count = sum(1 for source in non_marker_sources if _source_type(source) == "entity")
    fact_count = sum(1 for source in non_marker_sources if _source_type(source) == "factstate")

    return {
        "collection_name": collection_name,
        "status": "ready" if collection_name.casefold() in {name.casefold() for name in existing_names} else "not_found",
        "document_count": len(document_ids),
        "entity_count": entity_count,
        "fact_count": fact_count,
    }