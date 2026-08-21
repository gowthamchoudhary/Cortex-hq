"""Supabase service-role client for backend database operations.

Replaces the local SQLite stores used by ``auth/user_brains.py`` and
``identity/_store.py``.  The service-role key bypasses Row-Level Security
and is required for server-side writes.

Required env vars:
    SUPABASE_URL          – project URL (e.g. https://xxx.supabase.co)
    SUPABASE_SERVICE_KEY  – service-role key from Supabase dashboard

If SUPABASE_SERVICE_KEY is not set, falls back to SUPABASE_ANON_KEY
(service-role is strongly preferred for the backend).
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from supabase import Client, create_client


@lru_cache(maxsize=1)
def get_db_client() -> Client:
    """Return a Supabase client with service-role privileges."""
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_ANON_KEY")
    if not url or not key:
        raise RuntimeError(
            "Supabase is not configured: SUPABASE_URL and "
            "SUPABASE_SERVICE_KEY (or SUPABASE_ANON_KEY) are required."
        )
    return create_client(url, key)


# ---------------------------------------------------------------------------
# Table names — single source of truth for all Supabase table references
# ---------------------------------------------------------------------------

TABLE_USER_BRAINS = "user_brains"
TABLE_USER_IDENTITIES = "user_identities"
TABLE_EMPLOYEES = "employees"
TABLE_EXTERNAL_IDENTITIES = "external_identities"
TABLE_INVITATIONS = "invitations"
TABLE_EMAIL_VERIFICATIONS = "email_verifications"
TABLE_AGENTS = "agents"
TABLE_DEPLOYMENTS = "deployments"
TABLE_OAUTH_TOKENS = "oauth_tokens"
