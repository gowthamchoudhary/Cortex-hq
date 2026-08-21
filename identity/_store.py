"""Supabase-backed shared store for the identity layer.

Replaces the previous SQLite store (``identity/identity.db``).  The identity
layer tables — employees, external identities, invitations, and email
verification codes — are now stored in Supabase Postgres so they survive
Render free-tier deploys/restarts.

The public API is ``get_client()`` which returns a Supabase client with
service-role privileges.  Callers use the Supabase Python SDK directly.
"""

from __future__ import annotations

from auth.supabase_db import (
    get_db_client,
    TABLE_EMPLOYEES,
    TABLE_EXTERNAL_IDENTITIES,
    TABLE_INVITATIONS,
    TABLE_EMAIL_VERIFICATIONS,
)


def get_client():
    """Return a Supabase client with service-role privileges."""
    return get_db_client()


# Re-export table names for convenience
EMPLOYEES = TABLE_EMPLOYEES
EXTERNAL_IDENTITIES = TABLE_EXTERNAL_IDENTITIES
INVITATIONS = TABLE_INVITATIONS
EMAIL_VERIFICATIONS = TABLE_EMAIL_VERIFICATIONS
