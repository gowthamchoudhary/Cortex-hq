"""Admin invitation flow: email-verified invites that grant brain access.

An admin invites an employee by calling ``create_invitation(collection,
employee_id)``, which mints a token and returns an ``invite_url``. The employee
must first verify their work email (``identity.email_verification``); only then
does ``accept_invitation(token, user_id)`` succeed — it registers the user on
the brain via ``auth.user_brains`` with the employee's ``cortex_role``.
"""

from __future__ import annotations

import os
import secrets
import time
from typing import Any

from identity._store import connect
from identity.employee_directory import get_employee

INVITE_TTL_SECONDS = 7 * 24 * 3600  # 7 days
DEFAULT_APP_BASE_URL = "http://localhost:8501"
VALID_STATUSES = ("pending", "accepted", "revoked")


def _invite_base_url() -> str:
    return os.environ.get("CORTEX_APP_BASE_URL", DEFAULT_APP_BASE_URL).rstrip("/")


def _row_to_invitation(row: tuple[Any, ...]) -> dict[str, Any]:
    token, collection, employee_id, status, created_at, expires_at = row
    return {
        "token": token,
        "collection": collection,
        "employee_id": employee_id,
        "status": status,
        "created_at": created_at,
        "expires_at": expires_at,
    }


def create_invitation(collection: str, employee_id: str) -> dict[str, Any]:
    """Create a pending invite for an employee and return its URL.

    The employee must exist in the directory. The returned URL uses
    ``CORTEX_APP_BASE_URL`` (default ``http://localhost:8501``) so hosted
    deployments can point invites at the real app.
    """
    if not get_employee(collection, employee_id):
        raise KeyError(
            f"Unknown employee {employee_id!r} in collection {collection!r}; "
            "register_employee() first."
        )

    token = secrets.token_urlsafe(24)
    now = int(time.time())
    connection = connect()
    try:
        connection.execute(
            "INSERT INTO invitations (token, collection, employee_id, status, created_at, expires_at) "
            "VALUES (?, ?, ?, 'pending', ?, ?)",
            (token, str(collection).strip(), str(employee_id).strip(), now, now + INVITE_TTL_SECONDS),
        )
        connection.commit()
    finally:
        connection.close()

    return {
        "token": token,
        "invite_url": f"{_invite_base_url()}/invite/{token}",
        "collection": str(collection).strip(),
        "employee_id": str(employee_id).strip(),
        "status": "pending",
        "created_at": now,
        "expires_at": now + INVITE_TTL_SECONDS,
    }


def get_invitation(token: str) -> dict[str, Any] | None:
    """Return invitation details, or None when the token is unknown/expired."""
    if not str(token).strip():
        return None
    connection = connect()
    try:
        row = connection.execute(
            "SELECT * FROM invitations WHERE token = ?",
            (str(token).strip(),),
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        return None
    invitation = _row_to_invitation(row)
    if invitation["expires_at"] < int(time.time()):
        return None
    return invitation


def accept_invitation(token: str, user_id: str) -> dict[str, Any]:
    """Accept an invite: validate, check email verification, grant brain access.

    Returns one of:
    - ``{"status": "accepted", ...}`` — user registered on the brain.
    - ``{"status": "verification_required", ...}`` — invite is valid but the
      employee's work email has not been verified yet.
    - ``{"status": "failure", "reason": ...}`` — invalid/expired/used token or
      missing employee record.
    """
    if not str(user_id).strip():
        raise ValueError("user_id must not be empty.")

    invitation = get_invitation(token)
    if invitation is None:
        return {"status": "failure", "reason": "invalid_or_expired"}
    if invitation["status"] != "pending":
        return {"status": "failure", "reason": "already_used"}

    collection = invitation["collection"]
    employee = get_employee(collection, invitation["employee_id"])
    if employee is None:
        return {"status": "failure", "reason": "employee_not_found"}
    if not employee.get("work_email_verified"):
        return {
            "status": "verification_required",
            "collection": collection,
            "employee_id": invitation["employee_id"],
            "reason": (
                "Verify the employee's work email first via "
                "identity.email_verification.verify_email_code()."
            ),
        }

    from auth.user_brains import register_user_brain

    register_user_brain(str(user_id).strip(), collection, role=employee["cortex_role"])

    connection = connect()
    try:
        connection.execute(
            "UPDATE invitations SET status = 'accepted' WHERE token = ?",
            (str(token).strip(),),
        )
        connection.commit()
    finally:
        connection.close()

    return {
        "status": "accepted",
        "token": str(token).strip(),
        "collection": collection,
        "employee_id": invitation["employee_id"],
        "role": employee["cortex_role"],
    }
