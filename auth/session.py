"""Supabase session token validation.

Sign-in happens client-side through Supabase's hosted auth (Google OAuth).
This module only validates the access token a client sends after login and
extracts the authenticated user's identity.
"""

from __future__ import annotations

from typing import Any

from auth.supabase_client import get_supabase_client


def get_current_user(access_token: str) -> dict[str, str] | None:
    """Validate a Supabase access token.

    Returns ``{"user_id": ..., "email": ...}`` for a valid session or ``None``
    when the token is missing, expired, or invalid.
    """
    if not access_token or not str(access_token).strip():
        return None

    try:
        client = get_supabase_client()
        response = client.auth.get_user(str(access_token))
    except Exception:
        # Missing configuration, expired/invalid token, or network failure all
        # mean "not authenticated" to callers.
        return None

    user = getattr(response, "user", None) if response is not None else None
    if user is None:
        return None

    user_id = getattr(user, "id", None) or ""
    email = getattr(user, "email", None) or ""
    if not user_id:
        return None
    return {"user_id": str(user_id), "email": str(email)}
