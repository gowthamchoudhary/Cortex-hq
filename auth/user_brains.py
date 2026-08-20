"""SQLite mapping of authenticated users to knowledge-graph brains.

Mirrors the local-store pattern in ``deploy/agent_manager.py``: a small
``user_brains`` table maps ``(user_id, collection_name)`` to a role. The
default database lives at ``auth/user_brains.db`` and can be overridden with
the ``CORTEX_USER_BRAINS_DB`` environment variable.

A second table, ``user_identities``, optionally maps platform identities
(email addresses, WhatsApp phone numbers) to a Cortex ``user_id`` so inbound
adapters (email, WhatsApp, Slack, GitHub) can resolve the caller's role
without the caller being authenticated through Supabase.
"""

from __future__ import annotations

import os
import re
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

_SCHEMA_IDENTITIES = """
CREATE TABLE IF NOT EXISTS user_identities (
    user_id    TEXT PRIMARY KEY,
    email      TEXT UNIQUE,
    phone      TEXT UNIQUE,
    created_at INTEGER NOT NULL
);
"""

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_RE = re.compile(r"^\+?[0-9][0-9\s().-]{5,}$")


def _db_path() -> Path:
    override = os.environ.get("CORTEX_USER_BRAINS_DB")
    return Path(override) if override else DEFAULT_DB_PATH


def _connect() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path))
    connection.execute(_SCHEMA)
    connection.execute(_SCHEMA_IDENTITIES)
    connection.commit()
    return connection


def _normalize_email(email: str) -> str:
    return str(email).strip().lower()


def _normalize_phone(phone: str) -> str:
    """Collapse separators and store E.164-style with a leading +."""
    value = str(phone).strip()
    digits = re.sub(r"[^0-9]", "", value)
    if not digits:
        return ""
    return f"+{digits}"


def register_user_identity(
    user_id: str,
    email: str | None = None,
    phone: str | None = None,
) -> dict[str, Any]:
    """Attach an optional email and/or phone to a Cortex user id.

    These identities let inbound platform adapters resolve a caller's role:
    the runtime looks up ``user_id`` by email/phone, then reads the role from
    ``user_brains``. Upserts on ``user_id``; email/phone must be unique.
    """
    if not str(user_id).strip():
        raise ValueError("user_id must not be empty.")
    normalized_email = _normalize_email(email) if email else ""
    if normalized_email and not _EMAIL_RE.match(normalized_email):
        raise ValueError(f"Invalid email address {email!r}.")
    normalized_phone = _normalize_phone(phone) if phone else ""
    if normalized_phone and not _PHONE_RE.match(normalized_phone):
        raise ValueError(f"Invalid phone number {phone!r}.")

    connection = _connect()
    try:
        existing = connection.execute(
            "SELECT user_id FROM user_identities WHERE user_id = ?",
            (str(user_id).strip(),),
        ).fetchone()
        if existing:
            connection.execute(
                "UPDATE user_identities SET email = ?, phone = ?, created_at = ? "
                "WHERE user_id = ?",
                (normalized_email or None, normalized_phone or None, int(time.time()), str(user_id).strip()),
            )
        else:
            connection.execute(
                "INSERT INTO user_identities (user_id, email, phone, created_at) "
                "VALUES (?, ?, ?, ?)",
                (str(user_id).strip(), normalized_email or None, normalized_phone or None, int(time.time())),
            )
        connection.commit()
    except sqlite3.IntegrityError as exc:
        raise ValueError(
            f"Identity already registered to another user: {exc}"
        ) from exc
    finally:
        connection.close()

    return {
        "user_id": str(user_id).strip(),
        "email": normalized_email or None,
        "phone": normalized_phone or None,
    }


def get_user_id_by_identity(value: str) -> str | None:
    """Resolve any platform identity to a Cortex user id.

    Checks, in order: raw user_id match, normalized email match, normalized
    phone match. Returns None when nothing matches.
    """
    if not str(value).strip():
        return None
    raw = str(value).strip()
    candidates = [raw, _normalize_email(raw), _normalize_phone(raw)]
    connection = _connect()
    try:
        for candidate in candidates:
            row = connection.execute(
                "SELECT user_id FROM user_identities "
                "WHERE user_id = ? OR email = ? OR phone = ?",
                (candidate, candidate, candidate),
            ).fetchone()
            if row:
                return str(row[0])
    finally:
        connection.close()
    return None


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


def remove_user_brain(user_id: str, collection_name: str) -> bool:
    """Remove ``user_id``'s access to ``collection_name``. Returns True if a row was deleted."""
    if not str(user_id).strip() or not str(collection_name).strip():
        return False
    connection = _connect()
    try:
        cursor = connection.execute(
            "DELETE FROM user_brains WHERE user_id = ? AND collection_name = ?",
            (str(user_id).strip(), str(collection_name).strip()),
        )
        connection.commit()
        return cursor.rowcount > 0
    finally:
        connection.close()
