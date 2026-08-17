"""Canonical employee directory — the source of truth for who belongs to a brain.

Employees are keyed by ``(collection, employee_id)`` in the shared identity
SQLite store (``identity/_store.py``). Each employee carries a name, validated
work email, optional department/role title, the Cortex access role used for
question filtering (``admin``/``member``/``guest``), and an optional manager
reference that ``identity.org_graph`` turns into real ``manages`` edges in
HydraDB. The ``work_email_verified`` flag is set by
``identity.email_verification`` and gates invitation acceptance.
"""

from __future__ import annotations

import csv
import json
import re
import time
from pathlib import Path
from typing import Any

from identity._store import connect

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


def _row_to_employee(row: tuple[Any, ...]) -> dict[str, Any]:
    (
        collection,
        employee_id,
        name,
        work_email,
        department,
        role_title,
        cortex_role,
        manager_employee_id,
        work_email_verified,
        created_at,
        updated_at,
    ) = row
    return {
        "collection": collection,
        "employee_id": employee_id,
        "name": name,
        "work_email": work_email,
        "department": department,
        "role_title": role_title,
        "cortex_role": cortex_role,
        "manager_employee_id": manager_employee_id,
        "work_email_verified": bool(work_email_verified),
        "created_at": created_at,
        "updated_at": updated_at,
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
    """Upsert one employee into ``collection``'s directory.

    The record is keyed by ``(collection, employee_id)``; re-registering the
    same employee updates their record. Work emails are unique per collection,
    so registering a different employee_id with an existing email raises.
    """
    _validate_fields(collection, employee_id, name, work_email, cortex_role)
    now = int(time.time())

    connection = connect()
    try:
        connection.execute(
            "INSERT INTO employees ("
            "collection, employee_id, name, work_email, department, role_title, "
            "cortex_role, manager_employee_id, work_email_verified, created_at, updated_at"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?) "
            "ON CONFLICT (collection, employee_id) DO UPDATE SET "
            "name = excluded.name, work_email = excluded.work_email, "
            "department = excluded.department, role_title = excluded.role_title, "
            "cortex_role = excluded.cortex_role, "
            "manager_employee_id = excluded.manager_employee_id, "
            "updated_at = excluded.updated_at",
            (
                str(collection).strip(),
                str(employee_id).strip(),
                str(name).strip(),
                _normalize_email(work_email),
                department.strip() if department else None,
                role_title.strip() if role_title else None,
                _validate_role(cortex_role),
                manager_employee_id.strip() if manager_employee_id else None,
                now,
                now,
            ),
        )
        connection.commit()
    except Exception as exc:
        # sqlite3.IntegrityError (duplicate email for a different employee) and
        # any other write failure surface as a clear ValueError.
        raise ValueError(f"Failed to register employee {employee_id!r}: {exc}") from exc
    finally:
        connection.close()

    return get_employee(str(collection).strip(), str(employee_id).strip())  # type: ignore[return-value]


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
    """Register many employees at once and report per-item outcomes.

    ``employee_list`` is either a list of dicts (keys matching
    ``register_employee`` parameters) or a path to a CSV/JSON file. Individual
    failures are collected in ``errors`` and never abort the batch.
    """
    items = _load_employee_items(employee_list)
    summary: dict[str, Any] = {"added": 0, "updated": 0, "errors": []}
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            summary["errors"].append({"index": index, "item": item, "error": "not a dict"})
            continue
        try:
            # Determine insert-vs-update before writing so the summary stays
            # accurate even when register + update happen within one second.
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
    connection = connect()
    try:
        row = connection.execute(
            "SELECT * FROM employees WHERE collection = ? AND employee_id = ?",
            (str(collection).strip(), str(employee_id).strip()),
        ).fetchone()
    finally:
        connection.close()
    return _row_to_employee(row) if row else None


def update_employee(
    collection: str,
    employee_id: str,
    **fields: Any,
) -> dict[str, Any]:
    """Partially update an employee record.

    Allowed fields: ``name``, ``work_email``, ``department``, ``role_title``,
    ``cortex_role``, ``manager_employee_id``. Unknown fields raise ValueError.
    """
    if not get_employee(collection, employee_id):
        raise KeyError(f"Unknown employee {employee_id!r} in collection {collection!r}.")

    allowed = {"name", "work_email", "department", "role_title", "cortex_role", "manager_employee_id"}
    unknown = set(fields) - allowed
    if unknown:
        raise ValueError(f"Unknown employee fields: {', '.join(sorted(unknown))}.")

    # Validate before writing anything.
    current = get_employee(collection, employee_id)
    assert current is not None
    if "name" in fields and not str(fields["name"]).strip():
        raise ValueError("name must not be empty.")
    if "work_email" in fields and not _WORK_EMAIL_RE.match(_normalize_email(fields["work_email"])):
        raise ValueError(f"Invalid work_email {fields['work_email']!r}.")
    if "cortex_role" in fields:
        _validate_role(fields["cortex_role"])

    connection = connect()
    try:
        for field in sorted(fields):
            value = fields[field]
            if field in ("name", "work_email", "department", "role_title", "manager_employee_id"):
                if field == "work_email":
                    value = _normalize_email(value)
                value = value.strip() if value is not None else None
            elif field == "cortex_role":
                value = _validate_role(value)
            connection.execute(
                f"UPDATE employees SET {field} = ?, updated_at = ? "
                "WHERE collection = ? AND employee_id = ?",
                (value, int(time.time()), str(collection).strip(), str(employee_id).strip()),
            )
        connection.commit()
    except Exception as exc:
        raise ValueError(f"Failed to update employee {employee_id!r}: {exc}") from exc
    finally:
        connection.close()

    result = get_employee(str(collection).strip(), str(employee_id).strip())
    assert result is not None
    return result


def list_employees(collection: str) -> list[dict[str, Any]]:
    """Return every employee registered in ``collection``, ordered by employee_id."""
    connection = connect()
    try:
        rows = connection.execute(
            "SELECT * FROM employees WHERE collection = ? ORDER BY employee_id",
            (str(collection).strip(),),
        ).fetchall()
    finally:
        connection.close()
    return [_row_to_employee(row) for row in rows]
