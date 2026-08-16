"""Supabase client initialization.

The client is created lazily from ``SUPABASE_URL`` and ``SUPABASE_ANON_KEY``
environment variables so that importing this module never fails — only
actually creating a client (i.e. validating a session) requires the keys.
"""

from __future__ import annotations

import os
from functools import lru_cache

from supabase import Client, create_client


def get_supabase_client() -> Client:
    """Return a Supabase client, raising a clear error if it is not configured."""
    url = os.environ.get("SUPABASE_URL")
    anon_key = os.environ.get("SUPABASE_ANON_KEY")
    if not url or not anon_key:
        raise RuntimeError(
            "Supabase is not configured: SUPABASE_URL and SUPABASE_ANON_KEY "
            "environment variables are required."
        )
    return create_client(url, anon_key)


@lru_cache(maxsize=1)
def get_supabase_client_cached() -> Client:
    """Return a cached Supabase client for the lifetime of the process."""
    return get_supabase_client()
