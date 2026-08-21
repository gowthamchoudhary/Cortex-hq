"""Canonical employee directory — the source of truth for who belongs to a brain.

Employees are keyed by ``(collection, employee_id)`` in Supabase Postgres.
Each employee carries a name, validated work email, optional department/role
title, the Cortex access role used for question filtering
(``admin``/``member``/``guest``), and an optional manager reference that
``identity.org_graph`` turns into real ``manages`` edges in HydraDB.  The
``work_email_verified`` flag is set by ``identity.email_verification`` and
gates invitation acceptance.
"""

from __future__ import annotations

import csv
import json
import re
import time
from pathlib import Path
from typing import Any

from identity._store import get_client, EMPLOYEES

VALID_ROLES = ("admin", "member", "guest")
_WORK_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _normalize_email(email: str) -> str:
    return str(email).strip().lower()


def _validate_role(role: str) -> str:
    normalized_role = str(role).strip().lower()
    if normalized_role not in VALID_ROLES:
        raise ValueError(
            f"Unsupported cortex_role {role!r}; choose one of {', '.join(VALID_ROLES)}."
        )
    return normalized_role


def _row_to_employee(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "collection": row.get("collection", ""),
        "employee_id": row.get("employee_id", ""),
        "name": row.get("name", ""),
        "work_email": row.get("work_email", ""),
        "department": row.get("department"),
        "role_title": row.get("role_title"),
        "cortex_role": row.get("cortex_role", "member"),
        "manager_employee_id": row.get("manager_employee_id"),
        "work_email_verified": bool(row.get("work_email_verified", 0)),
        "created_at": row.get("created_at", 0),
        "updated_at": row.get("updated_at", 0),
    }


def _validate_fields(
    collection: str,
    employee_id: str,
    name: str,
    work_email: str,
    cortex_role: str,
) -> None:
    if not str(collection).strip():
        raise ValueError("collection must not be empty.")
    if not str(employee_id).strip():
        raise ValueError("employee_id must not be empty.")
    if not str(name).strip():
        raise ValueError("name must not be empty.")
    normalized_email = _normalize_email(work_email)
    if not _WORK_EMAIL_RE.match(normalized_email):
        raise ValueError(f"Invalid work_email {work_email!r}.")
    _validate_role(cortex_role)


def register_employee(
    collection: str,
    employee_id: str,
    name: str,
    work_email: str,
    department: str | None = None,
    role_title: str | None = None,
    cortex_role: str = "member",
    manager_employee_id: str | None = None,
) -> dict[str, Any]:
    """Upsert one employee into ``collection``'s directory."""
    _validate_fields(collection, employee_id, name, work_email, cortex_role)
    now = int(time.time())

    client = get_client()
    col = str(collection).strip()
    eid = str(employee_id).strip()

    data = {
        "collection": col,
        "employee_id": eid,
        "name": str(name).strip(),
        "work_email": _normalize_email(work_email),
        "department": department.strip() if department else None,
        "role_title": role_title.strip() if role_title else None,
        "cortex_role": _validate_role(cortex_role),
        "manager_employee_id": manager_employee_id.strip() if manager_employee_id else None,
        "work_email_verified": 0,
        "created_at": now,
        "updated_at": now,
    }

    try:
        client.table(EMPLOYEES).upsert(
            data,
            on_conflict="collection,employee_id",
        ).execute()
    except Exception as exc:
        raise ValueError(f"Failed to register employee {employee_id!r}: {exc}") from exc

    return get_employee(col, eid)  # type: ignore[return-value]


def _load_employee_items(source: Any) -> list[dict[str, Any]]:
    """Normalize bulk input: a list of dicts, or a CSV/JSON file path."""
    if isinstance(source, (str, Path)):
        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"Employee file not found: {path}")
        if path.suffix.lower() == ".csv":
            with path.open(newline="", encoding="utf-8-sig") as csv_file:
                return [dict(row) for row in csv.DictReader(csv_file)]
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if isinstance(data, dict):
            return list(data.get("employees") or data.get("records") or [data])
        if isinstance(data, list):
            return data
        raise ValueError(f"Unsupported employee file shape in {path}")
    if isinstance(source, list):
        return source
    raise ValueError("employee_list must be a list of dicts or a CSV/JSON file path.")


def bulk_register_employees(
    collection: str,
    employee_list: Any,
) -> dict[str, Any]:
    """Register many employees at once and report per-item outcomes."""
    items = _load_employee_items(employee_list)
    summary: dict[str, Any] = {"added": 0, "updated": 0, "errors": []}
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            summary["errors"].append({"index": index, "item": item, "error": "not a dict"})
            continue
        try:
            was_existing = get_employee(collection, str(item.get("employee_id") or "")) is not None
            register_employee(
                collection=collection,
                employee_id=str(item.get("employee_id") or ""),
                name=str(item.get("name") or ""),
                work_email=str(item.get("work_email") or ""),
                department=item.get("department"),
                role_title=item.get("role_title"),
                cortex_role=str(item.get("cortex_role") or "member"),
                manager_employee_id=item.get("manager_employee_id"),
            )
            summary["updated" if was_existing else "added"] += 1
        except ValueError as exc:
            summary["errors"].append(
                {
                    "index": index,
                    "employee_id": item.get("employee_id"),
                    "error": str(exc),
                }
            )
    return summary


def get_employee(collection: str, employee_id: str) -> dict[str, Any] | None:
    """Return the full employee record, or None when not registered."""
    client = get_client()
    result = (
        client.table(EMPLOYEES)
        .select("*")
        .eq("collection", str(collection).strip())
        .eq("employee_id", str(employee_id).strip())
        .limit(1)
        .execute()
    )
    if not result.data:
        return None
    return _row_to_employee(result.data[0])


def update_employee(
    collection: str,
    employee_id: str,
    **fields: Any,
) -> dict[str, Any]:
    """Partially update an employee record."""
    if not get_employee(collection, employee_id):
        raise KeyError(f"Unknown employee {employee_id!r} in collection {collection!r}.")

    allowed = {"name", "work_email", "department", "role_title", "cortex_role", "manager_employee_id"}
    unknown = set(fields) - allowed
    if unknown:
        raise ValueError(f"Unknown employee fields: {', '.join(sorted(unknown))}.")

    current = get_employee(collection, employee_id)
    assert current is not None
    if "name" in fields and not str(fields["name"]).strip():
        raise ValueError("name must not be empty.")
    if "work_email" in fields and not _WORK_EMAIL_RE.match(_normalize_email(fields["work_email"])):
        raise ValueError(f"Invalid work_email {fields['work_email']!r}.")
    if "cortex_role" in fields:
        _validate_role(fields["cortex_role"])

    client = get_client()
    update_data = {"updated_at": int(time.time())}
    for field in sorted(fields):
        value = fields[field]
        if field in ("name", "work_email", "department", "role_title", "manager_employee_id"):
            if field == "work_email":
                value = _normalize_email(value)
            value = value.strip() if value is not None else None
        elif field == "cortex_role":
            value = _validate_role(value)
        update_data[field] = value

    try:
        client.table(EMPLOYEES).update(update_data).eq(
            "collection", str(collection).strip()
        ).eq("employee_id", str(employee_id).strip()).execute()
    except Exception as exc:
        raise ValueError(f"Failed to update employee {employee_id!r}: {exc}") from exc

    result = get_employee(str(collection).strip(), str(employee_id).strip())
    assert result is not None
    return result


def list_employees(collection: str) -> list[dict[str, Any]]:
    """Return every employee registered in ``collection``, ordered by employee_id."""
    client = get_client()
    result = (
        client.table(EMPLOYEES)
        .select("*")
        .eq("collection", str(collection).strip())
        .order("employee_id")
        .execute()
    )
    return [_row_to_employee(row) for row in result.data]
