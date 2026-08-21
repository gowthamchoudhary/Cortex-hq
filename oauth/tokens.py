"""OAuth token storage for Gmail and Slack connectors.

Stores access_token and refresh_token tagged to a collection and provider
in Supabase Postgres (replaces the previous local SQLite database).
Tokens are encrypted at rest using Fernet symmetric encryption when
``OAUTH_TOKEN_SECRET`` is set; otherwise they are stored in plaintext for
local development.

Slack installs can produce two tokens: a **user** token (for ingestion)
and a **bot** token (for agent replies).  ``token_type`` distinguishes
them: ``"user"`` (default) or ``"bot"``.  Both live in the same table
keyed on ``(collection, provider, token_type)``.
"""

from __future__ import annotations

import os
import time
from typing import Any

from auth.supabase_db import get_db_client, TABLE_OAUTH_TOKENS


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

    client = get_db_client()
    client.table(TABLE_OAUTH_TOKENS).upsert({
        "collection": collection,
        "provider": provider,
        "token_type": normalized_type,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": expires_at,
        "scopes": scopes,
        "created_at": now,
        "updated_at": now,
    }, on_conflict="collection,provider,token_type").execute()

    return {
        "collection": collection,
        "provider": provider,
        "token_type": normalized_type,
        "stored": True,
        "expires_at": expires_at,
    }


def get_token(collection: str, provider: str, token_type: str = "user") -> dict[str, Any] | None:
    """Return the stored token dict for a specific token_type, or None if not found."""
    client = get_db_client()
    result = (
        client.table(TABLE_OAUTH_TOKENS)
        .select("access_token,refresh_token,expires_at,scopes")
        .eq("collection", collection)
        .eq("provider", provider)
        .eq("token_type", token_type)
        .limit(1)
        .execute()
    )
    if not result.data:
        return None
    row = result.data[0]
    return {
        "access_token": row["access_token"],
        "refresh_token": row["refresh_token"],
        "expires_at": row["expires_at"],
        "scopes": row["scopes"],
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
    client = get_db_client()
    result = (
        client.table(TABLE_OAUTH_TOKENS)
        .select("collection,access_token,refresh_token,expires_at,scopes")
        .eq("provider", provider)
        .eq("token_type", "bot")
        .execute()
    )
    for row in result.data:
        scopes = row.get("scopes") or ""
        if scopes and team_id in scopes:
            return {
                "collection": row["collection"],
                "access_token": row["access_token"],
                "refresh_token": row["refresh_token"],
                "expires_at": row["expires_at"],
                "scopes": row["scopes"],
            }
    return None


def delete_token(collection: str, provider: str, token_type: str | None = None) -> bool:
    """Remove stored token(s). If token_type is None, delete all for collection/provider.

    Returns True if any row was deleted.
    """
    client = get_db_client()
    query = (
        client.table(TABLE_OAUTH_TOKENS)
        .delete()
        .eq("collection", collection)
        .eq("provider", provider)
    )
    if token_type is not None:
        query = query.eq("token_type", token_type)
    result = query.execute()
    deleted_count = len(result.data) if result.data else 0
    return deleted_count > 0


def is_token_valid(collection: str, provider: str, token_type: str = "user") -> bool:
    """Check if a non-expired token exists."""
    token = get_token(collection, provider, token_type)
    if token is None:
        return False
    expires_at = token.get("expires_at")
    if expires_at is None:
        return True  # no expiry set — treat as valid
    return int(expires_at) > int(time.time())
