"""Read-only People & Access aggregation for a brain's employee directory.

A UI "People & Access" page calls ``get_people_access_data(collection)``
directly — same pattern as ``dashboard/admin_stats.py``. It never writes; it
combines the local employee directory (``identity.employee_directory``) with
the HydraDB graph to report, per employee, their directory record, linked
platform identities, and how many documents/facts their role can actually see
(role access filtering reused from ``reasoning.answer_question``).
"""

from __future__ import annotations

import os
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


def _api_key() -> str:
    api_key = os.environ.get("HYDRADB_API_KEY")
    if not api_key:
        raise RuntimeError("HYDRADB_API_KEY environment variable is required.")
    return api_key


def _list_sources(client: HydraDB, collection: str) -> list[dict[str, Any]]:
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
        sources.extend(source for source in (data.get("sources") or []) if isinstance(source, dict))
        pagination = _mapping(data.get("pagination"))
        if not pagination.get("has_next"):
            break
        page += 1
    return sources


def _role_access_summary(
    sources: list[dict[str, Any]],
    role: str,
) -> dict[str, Any]:
    """Count visible documents/facts for a role using answer_question's filter."""
    from reasoning.answer_question import allowed_access_levels

    allowed = sorted(allowed_access_levels(role))
    visible_documents: set[str] = set()
    visible_facts = 0
    for record in sources:
        access_level = str(_record_value(record, "access_level") or "public").strip().lower()
        if access_level not in allowed:
            continue
        if _record_type(record) == "factstate":
            visible_facts += 1
        doc_id = str(_record_value(record, "source_doc_id") or "").strip()
        if doc_id:
            visible_documents.add(doc_id)
    visible_documents.discard("")
    return {
        "visible_documents": len(visible_documents),
        "visible_facts": visible_facts,
        "access_levels": allowed,
    }


def get_people_access_data(collection: str) -> list[dict[str, Any]]:
    """Return one access summary row per employee in ``collection``.

    Each row: ``employee_id``, ``name``, ``work_email``, ``department``,
    ``role_title``, ``cortex_role``, ``manager_employee_id``,
    ``linked_platforms`` (from ``identity.external_identities``), and
    ``access_summary`` (visible document/fact counts for that role).
    """
    if not str(collection).strip():
        raise ValueError("collection must not be empty.")

    from identity.employee_directory import list_employees
    from identity.external_identities import list_linked_identities

    employees = list_employees(str(collection).strip())
    if not employees:
        return []

    client = HydraDB(token=_api_key())
    sources = _list_sources(client, str(collection).strip())
    # Cache the aggregation per role (employees share roles).
    access_cache: dict[str, dict[str, Any]] = {}

    rows: list[dict[str, Any]] = []
    for employee in employees:
        role = employee["cortex_role"]
        if role not in access_cache:
            access_cache[role] = _role_access_summary(sources, role)
        rows.append(
            {
                "employee_id": employee["employee_id"],
                "name": employee["name"],
                "work_email": employee["work_email"],
                "department": employee["department"],
                "role_title": employee["role_title"],
                "cortex_role": role,
                "manager_employee_id": employee["manager_employee_id"],
                "linked_platforms": list_linked_identities(
                    str(collection).strip(), employee["employee_id"]
                ),
                "access_summary": dict(access_cache[role]),
            }
        )
    return rows
