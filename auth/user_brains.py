"""Supabase-backed mapping of authenticated users to knowledge-graph brains.

Mirrors the interface of the previous SQLite version: a ``user_brains`` table
maps ``(user_id, collection_name)`` to a role.  Data is now stored in
Supabase Postgres so it survives Render free-tier deploys/restarts.

A second table, ``user_identities``, optionally maps platform identities
(email addresses, WhatsApp phone numbers) to a Cortex ``user_id`` so inbound
adapters (email, WhatsApp, Slack, GitHub) can resolve the caller's role
without the caller being authenticated through Supabase.
"""

from __future__ import annotations

import re
import time
from typing import Any

from auth.supabase_db import (
    get_db_client,
    TABLE_USER_BRAINS,
    TABLE_USER_IDENTITIES,
)

VALID_ROLES = ("admin", "member", "guest")

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_RE = re.compile(r"^\+?[0-9][0-9\s().-]{5,}$")


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
    """Attach an optional email and/or phone to a Cortex user id."""
    if not str(user_id).strip():
        raise ValueError("user_id must not be empty.")
    normalized_email = _normalize_email(email) if email else ""
    if normalized_email and not _EMAIL_RE.match(normalized_email):
        raise ValueError(f"Invalid email address {email!r}.")
    normalized_phone = _normalize_phone(phone) if phone else ""
    if normalized_phone and not _PHONE_RE.match(normalized_phone):
        raise ValueError(f"Invalid phone number {phone!r}.")

    client = get_db_client()
    uid = str(user_id).strip()

    existing = (
        client.table(TABLE_USER_IDENTITIES)
        .select("user_id")
        .eq("user_id", uid)
        .execute()
    )

    data = {
        "user_id": uid,
        "email": normalized_email or None,
        "phone": normalized_phone or None,
        "created_at": int(time.time()),
    }

    if existing.data:
        client.table(TABLE_USER_IDENTITIES).update(data).eq("user_id", uid).execute()
    else:
        client.table(TABLE_USER_IDENTITIES).insert(data).execute()

    return {
        "user_id": uid,
        "email": normalized_email or None,
        "phone": normalized_phone or None,
    }


def get_user_id_by_identity(value: str) -> str | None:
    """Resolve any platform identity to a Cortex user id."""
    if not str(value).strip():
        return None
    raw = str(value).strip()
    candidates = [raw, _normalize_email(raw), _normalize_phone(raw)]

    client = get_db_client()
    for candidate in candidates:
        result = (
            client.table(TABLE_USER_IDENTITIES)
            .select("user_id")
            .or_(f"user_id.eq.{candidate},email.eq.{candidate},phone.eq.{candidate}")
            .limit(1)
            .execute()
        )
        if result.data:
            return str(result.data[0]["user_id"])
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

    uid = str(user_id).strip()
    col = str(collection_name).strip()
    client = get_db_client()

    # Supabase upsert: insert or update on PK conflict
    client.table(TABLE_USER_BRAINS).upsert(
        {
            "user_id": uid,
            "collection_name": col,
            "role": normalized_role,
            "created_at": int(time.time()),
        },
        on_conflict="user_id,collection_name",
    ).execute()

    return {
        "user_id": uid,
        "collection_name": col,
        "role": normalized_role,
    }


def get_user_brains(user_id: str) -> list[dict[str, str]]:
    """Return all brain grants for ``user_id``."""
    client = get_db_client()
    result = (
        client.table(TABLE_USER_BRAINS)
        .select("collection_name,role")
        .eq("user_id", str(user_id))
        .order("collection_name")
        .execute()
    )
    return [
        {"collection_name": row["collection_name"], "role": row["role"]}
        for row in result.data
    ]


def get_user_role_in_brain(user_id: str, collection_name: str) -> str | None:
    """Return the role for ``user_id`` in ``collection_name``, or None."""
    client = get_db_client()
    result = (
        client.table(TABLE_USER_BRAINS)
        .select("role")
        .eq("user_id", str(user_id))
        .eq("collection_name", str(collection_name))
        .limit(1)
        .execute()
    )
    return str(result.data[0]["role"]) if result.data else None


def remove_user_brain(user_id: str, collection_name: str) -> bool:
    """Remove ``user_id``'s access to ``collection_name``. Returns True if a row was deleted."""
    if not str(user_id).strip() or not str(collection_name).strip():
        return False

    client = get_db_client()
    result = (
        client.table(TABLE_USER_BRAINS)
        .delete()
        .eq("user_id", str(user_id).strip())
        .eq("collection_name", str(collection_name).strip())
        .execute()
    )
    # Supabase delete returns deleted rows in .data
    deleted_count = len(result.data) if result.data else 0
    return deleted_count > 0
