"""SQLite mapping of authenticated users to knowledge-graph brains.

Mirrors the local-store pattern in ``deploy/agent_manager.py``: a small
``user_brains`` table maps ``(user_id, collection_name)`` to a role. The
default database lives at ``auth/user_brains.db`` and can be overridden with
the ``CORTEX_USER_BRAINS_DB`` environment variable.
"""

from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path
from typing import Any

AUTH_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = AUTH_DIR / "user_brains.db"

VALID_ROLES = ("admin", "member", "guest")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS user_brains (
    user_id         TEXT NOT NULL,
    collection_name TEXT NOT NULL,
    role            TEXT NOT NULL,
    created_at      INTEGER NOT NULL,
    PRIMARY KEY (user_id, collection_name)
);
"""


def _db_path() -> Path:
    override = os.environ.get("CORTEX_USER_BRAINS_DB")
    return Path(override) if override else DEFAULT_DB_PATH


def _connect() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path))
    connection.execute(_SCHEMA)
    connection.commit()
    return connection


def _validate_role(role: str) -> str:
    normalized_role = str(role).strip().lower()
    if normalized_role not in VALID_ROLES:
        raise ValueError(
            f"Unsupported role {role!r}; choose one of {', '.join(VALID_ROLES)}."
        )
    return normalized_role


def register_user_brain(
    user_id: str,
    collection_name: str,
    role: str = "admin",
) -> dict[str, str]:
    """Grant ``user_id`` access to a brain collection.

    The mapping is upserted on ``(user_id, collection_name)`` — calling again
    with a new role updates the existing grant.
    """
    if not str(user_id).strip():
        raise ValueError("user_id must not be empty.")
    if not str(collection_name).strip():
        raise ValueError("collection_name must not be empty.")
    normalized_role = _validate_role(role)

    connection = _connect()
    try:
        connection.execute(
            "INSERT INTO user_brains (user_id, collection_name, role, created_at) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT (user_id, collection_name) "
            "DO UPDATE SET role = excluded.role",
            (
                str(user_id).strip(),
                str(collection_name).strip(),
                normalized_role,
                int(time.time()),
            ),
        )
        connection.commit()
    finally:
        connection.close()

    return {
        "user_id": str(user_id).strip(),
        "collection_name": str(collection_name).strip(),
        "role": normalized_role,
    }


def get_user_brains(user_id: str) -> list[dict[str, str]]:
    """Return all brain grants for ``user_id``."""
    connection = _connect()
    try:
        rows = connection.execute(
            "SELECT collection_name, role FROM user_brains "
            "WHERE user_id = ? ORDER BY collection_name",
            (str(user_id),),
        ).fetchall()
    finally:
        connection.close()

    return [
        {"collection_name": collection_name, "role": role}
        for collection_name, role in rows
    ]


def get_user_role_in_brain(user_id: str, collection_name: str) -> str | None:
    """Return the role for ``user_id`` in ``collection_name``, or None."""
    connection = _connect()
    try:
        row = connection.execute(
            "SELECT role FROM user_brains "
            "WHERE user_id = ? AND collection_name = ?",
            (str(user_id), str(collection_name)),
        ).fetchone()
    finally:
        connection.close()

    return str(row[0]) if row else None
