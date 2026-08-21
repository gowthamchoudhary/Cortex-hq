"""External identity linking — platform users route through employees, not roles.

Adapters (Slack, GitHub, email, WhatsApp) hand the runtime a platform identity
(a Slack user id, GitHub username, email address, or WhatsApp phone number).
This module maps those to an ``employee_id`` in a collection, so the role used
for answering is always the employee's ``cortex_role`` from the directory —
never a direct platform-to-role mapping.

Data is stored in Supabase Postgres so it survives Render deploys/restarts.
"""

from __future__ import annotations

import re
import time
from typing import Any

from identity._store import get_client, EXTERNAL_IDENTITIES
from identity.employee_directory import get_employee

VALID_PLATFORMS = ("slack", "github", "email", "whatsapp")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _normalize_platform_user_id(platform: str, platform_user_id: str) -> str:
    """Normalize a platform identity for storage and lookup."""
    value = str(platform_user_id).strip()
    if platform == "email":
        value = value.lower()
        if not _EMAIL_RE.match(value):
            raise ValueError(f"Invalid email address {platform_user_id!r}.")
    elif platform == "whatsapp":
        digits = re.sub(r"[^0-9]", "", value)
        if not digits:
            raise ValueError(f"Invalid phone number {platform_user_id!r}.")
        value = f"+{digits}"
    return value


def link_external_identity(
    collection: str,
    employee_id: str,
    platform: str,
    platform_user_id: str,
) -> dict[str, Any]:
    """Link a platform identity to an employee in ``collection``."""
    normalized_platform = str(platform).strip().lower()
    if normalized_platform not in VALID_PLATFORMS:
        raise ValueError(
            f"Unsupported platform {platform!r}; choose one of {', '.join(VALID_PLATFORMS)}."
        )
    if not get_employee(collection, employee_id):
        raise KeyError(
            f"Unknown employee {employee_id!r} in collection {collection!r}; "
            "register_employee() first."
        )
    normalized_user_id = _normalize_platform_user_id(normalized_platform, platform_user_id)

    client = get_client()
    client.table(EXTERNAL_IDENTITIES).upsert({
        "collection": str(collection).strip(),
        "platform": normalized_platform,
        "platform_user_id": normalized_user_id,
        "employee_id": str(employee_id).strip(),
        "created_at": int(time.time()),
    }, on_conflict="collection,platform,platform_user_id").execute()

    return {
        "collection": str(collection).strip(),
        "platform": normalized_platform,
        "platform_user_id": normalized_user_id,
        "employee_id": str(employee_id).strip(),
    }


def resolve_platform_user(
    collection: str,
    platform: str,
    platform_user_id: str,
) -> str | None:
    """Map a platform identity to an employee_id, or None when unlinked."""
    normalized_platform = str(platform).strip().lower()
    if normalized_platform not in VALID_PLATFORMS:
        raise ValueError(
            f"Unsupported platform {platform!r}; choose one of {', '.join(VALID_PLATFORMS)}."
        )
    try:
        normalized_user_id = _normalize_platform_user_id(normalized_platform, platform_user_id)
    except ValueError:
        return None

    client = get_client()
    result = (
        client.table(EXTERNAL_IDENTITIES)
        .select("employee_id")
        .eq("collection", str(collection).strip())
        .eq("platform", normalized_platform)
        .eq("platform_user_id", normalized_user_id)
        .limit(1)
        .execute()
    )
    return str(result.data[0]["employee_id"]) if result.data else None


def unlink_external_identity(
    collection: str,
    platform: str,
    platform_user_id: str,
) -> bool:
    """Remove a platform identity link. Returns True when a link was removed."""
    normalized_platform = str(platform).strip().lower()
    if normalized_platform not in VALID_PLATFORMS:
        raise ValueError(
            f"Unsupported platform {platform!r}; choose one of {', '.join(VALID_PLATFORMS)}."
        )
    normalized_user_id = _normalize_platform_user_id(normalized_platform, platform_user_id)

    client = get_client()
    result = (
        client.table(EXTERNAL_IDENTITIES)
        .delete()
        .eq("collection", str(collection).strip())
        .eq("platform", normalized_platform)
        .eq("platform_user_id", normalized_user_id)
        .execute()
    )
    deleted_count = len(result.data) if result.data else 0
    return deleted_count > 0


def list_linked_identities(
    collection: str,
    employee_id: str,
) -> list[dict[str, str]]:
    """Return every platform identity linked to ``employee_id``."""
    client = get_client()
    result = (
        client.table(EXTERNAL_IDENTITIES)
        .select("platform,platform_user_id")
        .eq("collection", str(collection).strip())
        .eq("employee_id", str(employee_id).strip())
        .order("platform")
        .execute()
    )
    return [
        {"platform": row["platform"], "platform_user_id": row["platform_user_id"]}
        for row in result.data
    ]
