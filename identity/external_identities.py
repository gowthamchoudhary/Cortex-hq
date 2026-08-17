"""External identity linking — platform users route through employees, not roles.

Adapters (Slack, GitHub, email, WhatsApp) hand the runtime a platform identity
(a Slack user id, GitHub username, email address, or WhatsApp phone number).
This module maps those to an ``employee_id`` in a collection, so the role used
for answering is always the employee's ``cortex_role`` from the directory —
never a direct platform-to-role mapping.
"""

from __future__ import annotations

import re
import time
from typing import Any

from identity._store import connect
from identity.employee_directory import get_employee

VALID_PLATFORMS = ("slack", "github", "email", "whatsapp")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _normalize_platform_user_id(platform: str, platform_user_id: str) -> str:
    """Normalize a platform identity for storage and lookup.

    Email addresses are lowercased; WhatsApp phone numbers are stored
    E.164-style with a leading ``+`` (matching ``auth.user_brains``). Slack
    user ids and GitHub usernames are used verbatim.
    """
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
    """Link a platform identity to an employee in ``collection``.

    The employee must already exist in the directory (``register_employee``
    first). Linking is upserted on ``(collection, platform, platform_user_id)``.
    """
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

    connection = connect()
    try:
        connection.execute(
            "INSERT INTO external_identities (collection, platform, platform_user_id, employee_id, created_at) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT (collection, platform, platform_user_id) "
            "DO UPDATE SET employee_id = excluded.employee_id",
            (
                str(collection).strip(),
                normalized_platform,
                normalized_user_id,
                str(employee_id).strip(),
                int(time.time()),
            ),
        )
        connection.commit()
    finally:
        connection.close()

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

    connection = connect()
    try:
        row = connection.execute(
            "SELECT employee_id FROM external_identities "
            "WHERE collection = ? AND platform = ? AND platform_user_id = ?",
            (str(collection).strip(), normalized_platform, normalized_user_id),
        ).fetchone()
    finally:
        connection.close()
    return str(row[0]) if row else None


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

    connection = connect()
    try:
        cursor = connection.execute(
            "DELETE FROM external_identities "
            "WHERE collection = ? AND platform = ? AND platform_user_id = ?",
            (str(collection).strip(), normalized_platform, normalized_user_id),
        )
        connection.commit()
        return cursor.rowcount > 0
    finally:
        connection.close()


def list_linked_identities(
    collection: str,
    employee_id: str,
) -> list[dict[str, str]]:
    """Return every platform identity linked to ``employee_id``."""
    connection = connect()
    try:
        rows = connection.execute(
            "SELECT platform, platform_user_id FROM external_identities "
            "WHERE collection = ? AND employee_id = ? ORDER BY platform",
            (str(collection).strip(), str(employee_id).strip()),
        ).fetchall()
    finally:
        connection.close()
    return [
        {"platform": platform, "platform_user_id": platform_user_id}
        for platform, platform_user_id in rows
    ]
