"""Shared SQLite store for the identity layer.

One database file (``identity/identity.db``, override with ``CORTEX_IDENTITY_DB``)
holds the four identity-layer tables — the employee directory, external
platform identities, invitations, and email verification codes. This mirrors
the local-store pattern from ``auth/user_brains.py`` and ``deploy/agent_manager.py``.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

IDENTITY_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = IDENTITY_DIR / "identity.db"

# SQLite's driver executes one statement per execute(); keep every schema
# string a single statement so _connect() works on any supported version.
_SCHEMAS = (
    """CREATE TABLE IF NOT EXISTS employees (
        collection          TEXT NOT NULL,
        employee_id         TEXT NOT NULL,
        name                TEXT NOT NULL,
        work_email          TEXT NOT NULL,
        department          TEXT,
        role_title          TEXT,
        cortex_role         TEXT NOT NULL,
        manager_employee_id TEXT,
        work_email_verified INTEGER NOT NULL DEFAULT 0,
        created_at          INTEGER NOT NULL,
        updated_at          INTEGER NOT NULL,
        PRIMARY KEY (collection, employee_id),
        UNIQUE (collection, work_email)
    );""",
    """CREATE TABLE IF NOT EXISTS external_identities (
        collection       TEXT NOT NULL,
        platform         TEXT NOT NULL,
        platform_user_id TEXT NOT NULL,
        employee_id      TEXT NOT NULL,
        created_at       INTEGER NOT NULL,
        PRIMARY KEY (collection, platform, platform_user_id)
    );""",
    """CREATE TABLE IF NOT EXISTS invitations (
        token       TEXT PRIMARY KEY,
        collection  TEXT NOT NULL,
        employee_id TEXT NOT NULL,
        status      TEXT NOT NULL,
        created_at  INTEGER NOT NULL,
        expires_at  INTEGER NOT NULL
    );""",
    """CREATE TABLE IF NOT EXISTS email_verifications (
        email       TEXT NOT NULL,
        code        TEXT NOT NULL,
        employee_id TEXT NOT NULL,
        created_at  INTEGER NOT NULL,
        expires_at  INTEGER NOT NULL,
        PRIMARY KEY (email, code)
    );""",
)


def db_path() -> Path:
    """Return the identity store path, honoring the CORTEX_IDENTITY_DB override."""
    override = os.environ.get("CORTEX_IDENTITY_DB")
    return Path(override) if override else DEFAULT_DB_PATH


def connect() -> sqlite3.Connection:
    """Open the identity store, creating all tables if missing."""
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path))
    for schema in _SCHEMAS:
        connection.execute(schema)
    connection.commit()
    return connection
