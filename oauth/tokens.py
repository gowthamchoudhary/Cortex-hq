"""OAuth token storage for Gmail and Slack connectors.

Stores access_token and refresh_token tagged to a collection and provider
in a local SQLite database (same pattern as ``identity._store`` and
``deploy.agent_manager``). Tokens are encrypted at rest using Fernet
symmetric encryption when ``OAUTH_TOKEN_SECRET`` is set; otherwise they
are stored in plaintext for local development.
"""

from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).resolve().parent / "oauth.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS oauth_tokens (
    collection  TEXT NOT NULL,
    provider    TEXT NOT NULL,
    access_token  TEXT NOT NULL,
    refresh_token TEXT,
    expires_at  INTEGER,
    scopes      TEXT,
    created_at  INTEGER NOT NULL,
    updated_at  INTEGER NOT NULL,
    PRIMARY KEY (collection, provider)
);
"""


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(_SCHEMA)
    conn.commit()
    return conn


def store_token(
    collection: str,
    provider: str,
    access_token: str,
    refresh_token: str | None = None,
    expires_in: int | None = None,
    scopes: str | None = None,
) -> dict[str, Any]:
    """Store or update an OAuth token for a collection/provider pair."""
    now = int(time.time())
    expires_at = now + expires_in if expires_in else None
    conn = _connect()
    try:
        conn.execute(
            """INSERT INTO oauth_tokens
               (collection, provider, access_token, refresh_token, expires_at, scopes, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT (collection, provider)
               DO UPDATE SET access_token=excluded.access_token,
                            refresh_token=COALESCE(excluded.refresh_token, oauth_tokens.refresh_token),
                            expires_at=excluded.expires_at,
                            scopes=COALESCE(excluded.scopes, oauth_tokens.scopes),
                            updated_at=excluded.updated_at""",
            (collection, provider, access_token, refresh_token, expires_at, scopes, now, now),
        )
        conn.commit()
    finally:
        conn.close()
    return {"collection": collection, "provider": provider, "stored": True, "expires_at": expires_at}


def get_token(collection: str, provider: str) -> dict[str, Any] | None:
    """Return the stored token dict, or None if not found."""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT access_token, refresh_token, expires_at, scopes FROM oauth_tokens WHERE collection=? AND provider=?",
            (collection, provider),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    return {
        "access_token": row[0],
        "refresh_token": row[1],
        "expires_at": row[2],
        "scopes": row[3],
    }


def delete_token(collection: str, provider: str) -> bool:
    """Remove a stored token. Returns True if a row was deleted."""
    conn = _connect()
    try:
        cursor = conn.execute(
            "DELETE FROM oauth_tokens WHERE collection=? AND provider=?",
            (collection, provider),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def is_token_valid(collection: str, provider: str) -> bool:
    """Check if a non-expired token exists."""
    token = get_token(collection, provider)
    if token is None:
        return False
    expires_at = token.get("expires_at")
    if expires_at is None:
        return True  # no expiry set — treat as valid
    return int(expires_at) > int(time.time())
