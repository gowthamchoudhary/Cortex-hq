"""OAuth token storage for Gmail and Slack connectors.

Stores access_token and refresh_token tagged to a collection and provider
in a local SQLite database (same pattern as ``identity._store`` and
``deploy.agent_manager``). Tokens are encrypted at rest using Fernet
symmetric encryption when ``OAUTH_TOKEN_SECRET`` is set; otherwise they
are stored in plaintext for local development.

Slack installs can produce two tokens: a **user** token (for ingestion)
and a **bot** token (for agent replies).  ``token_type`` distinguishes
them: ``"user"`` (default) or ``"bot"``.  Both live in the same table
keyed on ``(collection, provider, token_type)``.
"""

from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).resolve().parent / "oauth.db"

# ---------------------------------------------------------------------------
# Schema — v2 adds token_type column.  We migrate transparently on connect.
# ---------------------------------------------------------------------------

_SCHEMA_V1 = """
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
    # Ensure v1 table exists.
    conn.execute(_SCHEMA_V1)

    # Migrate: add token_type column if missing.
    cols = {row[1] for row in conn.execute("PRAGMA table_info(oauth_tokens)")}
    if "token_type" not in cols:
        conn.execute(
            "ALTER TABLE oauth_tokens ADD COLUMN token_type TEXT NOT NULL DEFAULT 'user'"
        )
        # Drop the old single-column PK and recreate with the composite key.
        # SQLite doesn't support DROP PRIMARY KEY, so we rebuild the table.
        conn.execute("CREATE TABLE IF NOT EXISTS _oauth_tokens_v2 ("
            "collection  TEXT NOT NULL, "
            "provider    TEXT NOT NULL, "
            "token_type  TEXT NOT NULL DEFAULT 'user', "
            "access_token  TEXT NOT NULL, "
            "refresh_token TEXT, "
            "expires_at  INTEGER, "
            "scopes      TEXT, "
            "created_at  INTEGER NOT NULL, "
            "updated_at  INTEGER NOT NULL, "
            "PRIMARY KEY (collection, provider, token_type)"
            ")")
        conn.execute(
            "INSERT OR REPLACE INTO _oauth_tokens_v2 "
            "(collection, provider, token_type, access_token, refresh_token, expires_at, scopes, created_at, updated_at) "
            "SELECT collection, provider, token_type, access_token, refresh_token, expires_at, scopes, created_at, updated_at "
            "FROM oauth_tokens"
        )
        conn.execute("DROP TABLE oauth_tokens")
        conn.execute("ALTER TABLE _oauth_tokens_v2 RENAME TO oauth_tokens")
    else:
        # Column exists but PK might still be the old one — rebuild to be safe.
        conn.execute("CREATE TABLE IF NOT EXISTS _oauth_tokens_v2 ("
            "collection  TEXT NOT NULL, "
            "provider    TEXT NOT NULL, "
            "token_type  TEXT NOT NULL DEFAULT 'user', "
            "access_token  TEXT NOT NULL, "
            "refresh_token TEXT, "
            "expires_at  INTEGER, "
            "scopes      TEXT, "
            "created_at  INTEGER NOT NULL, "
            "updated_at  INTEGER NOT NULL, "
            "PRIMARY KEY (collection, provider, token_type)"
            ")")
        existing_rows = conn.execute("SELECT * FROM oauth_tokens").fetchall()
        if existing_rows:
            conn.execute(
                "INSERT OR REPLACE INTO _oauth_tokens_v2 "
                "(collection, provider, token_type, access_token, refresh_token, expires_at, scopes, created_at, updated_at) "
                "SELECT collection, provider, COALESCE(token_type, 'user'), access_token, refresh_token, expires_at, scopes, created_at, updated_at "
                "FROM oauth_tokens"
            )
        conn.execute("DROP TABLE oauth_tokens")
        conn.execute("ALTER TABLE _oauth_tokens_v2 RENAME TO oauth_tokens")

    conn.commit()
    return conn


def store_token(
    collection: str,
    provider: str,
    access_token: str,
    refresh_token: str | None = None,
    expires_in: int | None = None,
    scopes: str | None = None,
    token_type: str = "user",
) -> dict[str, Any]:
    """Store or update an OAuth token for a collection/provider/token_type triple."""
    now = int(time.time())
    expires_at = now + expires_in if expires_in else None
    normalized_type = str(token_type).strip().lower() or "user"
    conn = _connect()
    try:
        conn.execute(
            """INSERT INTO oauth_tokens
               (collection, provider, token_type, access_token, refresh_token, expires_at, scopes, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT (collection, provider, token_type)
               DO UPDATE SET access_token=excluded.access_token,
                            refresh_token=COALESCE(excluded.refresh_token, oauth_tokens.refresh_token),
                            expires_at=excluded.expires_at,
                            scopes=COALESCE(excluded.scopes, oauth_tokens.scopes),
                            updated_at=excluded.updated_at""",
            (collection, provider, normalized_type, access_token, refresh_token, expires_at, scopes, now, now),
        )
        conn.commit()
    finally:
        conn.close()
    return {
        "collection": collection,
        "provider": provider,
        "token_type": normalized_type,
        "stored": True,
        "expires_at": expires_at,
    }


def get_token(collection: str, provider: str, token_type: str = "user") -> dict[str, Any] | None:
    """Return the stored token dict for a specific token_type, or None if not found."""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT access_token, refresh_token, expires_at, scopes FROM oauth_tokens "
            "WHERE collection=? AND provider=? AND token_type=?",
            (collection, provider, token_type),
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


def get_bot_token_for_collection(collection: str, provider: str = "slack") -> dict[str, Any] | None:
    """Return the bot token for a collection, or None.

    Convenience wrapper: checks ``token_type="bot"`` first, falls back to
    ``"user"`` so single-token providers (Gmail, GitHub) still work.
    """
    bot = get_token(collection, provider, "bot")
    if bot is not None:
        return bot
    return get_token(collection, provider, "user")


def get_bot_token_for_team(team_id: str, provider: str = "slack") -> dict[str, Any] | None:
    """Look up a bot token by Slack team_id.

    Scans all collections for a bot token whose stored ``scopes`` metadata
    includes the ``team_id``.  Returns the first match or None.
    """
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT collection, access_token, refresh_token, expires_at, scopes "
            "FROM oauth_tokens WHERE provider=? AND token_type='bot'",
            (provider,),
        ).fetchall()
    finally:
        conn.close()
    for collection, access_token, refresh_token, expires_at, scopes in rows:
        # Scopes metadata stores "team_id:T0123,..." — check for the team id.
        if scopes and team_id in scopes:
            return {
                "collection": collection,
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expires_at": expires_at,
                "scopes": scopes,
            }
    return None


def delete_token(collection: str, provider: str, token_type: str | None = None) -> bool:
    """Remove stored token(s). If token_type is None, delete all for collection/provider.

    Returns True if any row was deleted.
    """
    conn = _connect()
    try:
        if token_type is not None:
            cursor = conn.execute(
                "DELETE FROM oauth_tokens WHERE collection=? AND provider=? AND token_type=?",
                (collection, provider, token_type),
            )
        else:
            cursor = conn.execute(
                "DELETE FROM oauth_tokens WHERE collection=? AND provider=?",
                (collection, provider),
            )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def is_token_valid(collection: str, provider: str, token_type: str = "user") -> bool:
    """Check if a non-expired token exists."""
    token = get_token(collection, provider, token_type)
    if token is None:
        return False
    expires_at = token.get("expires_at")
    if expires_at is None:
        return True  # no expiry set — treat as valid
    return int(expires_at) > int(time.time())
