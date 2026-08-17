"""Verified-work-email second factor (lightweight SSO stand-in).

Full enterprise SSO is out of scope for a custom IdP, so Cortex uses the
verified-work-email pattern as its "second factor": a 6-digit code sent to the
employee's work email, valid for 10 minutes. ``accept_invitation`` refuses to
grant access until the employee's work email is verified, which forces invitees
to prove they control the company email address attached to their directory
record.

Codes are stored in the shared identity SQLite store and sent through the
existing SendGrid setup in ``deploy.adapters.email_adapter`` (``SENDGRID_API_KEY``
+ ``CORTEX_EMAIL_FROM`` required at send time).
"""

from __future__ import annotations

import os
import random
import time
from typing import Any

from identity._store import connect
from identity.employee_directory import get_employee

VERIFICATION_TTL_SECONDS = 10 * 60  # 10 minutes
_CODE_DIGITS = 6


def _normalize_email(email: str) -> str:
    return str(email).strip().lower()


def _find_employee_by_email_and_id(email: str, employee_id: str) -> dict[str, Any] | None:
    """Locate the employee across collections matching (employee_id, work_email)."""
    connection = connect()
    try:
        row = connection.execute(
            "SELECT collection FROM employees WHERE employee_id = ? AND work_email = ?",
            (str(employee_id).strip(), _normalize_email(email)),
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        return None
    return get_employee(row[0], str(employee_id).strip())


def send_verification_email(email: str, employee_id: str) -> dict[str, Any]:
    """Generate a 6-digit code, store it with a 10-minute expiry, and email it.

    The ``(employee_id, work_email)`` pair must match a registered employee, so
    codes can only be issued to addresses the directory already knows. The live
    send goes through ``deploy.adapters.email_adapter.send_email_reply`` and
    raises a clear error when SendGrid env vars are missing.
    """
    normalized_email = _normalize_email(email)
    employee = _find_employee_by_email_and_id(normalized_email, employee_id)
    if employee is None:
        raise ValueError(
            f"No employee matches employee_id {employee_id!r} with work_email {email!r}."
        )

    code = "".join(str(random.SystemRandom().randrange(10)) for _ in range(_CODE_DIGITS))
    now = int(time.time())
    connection = connect()
    try:
        connection.execute(
            "INSERT INTO email_verifications (email, code, employee_id, created_at, expires_at) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT (email, code) DO UPDATE SET "
            "employee_id = excluded.employee_id, "
            "created_at = excluded.created_at, expires_at = excluded.expires_at",
            (normalized_email, code, str(employee_id).strip(), now, now + VERIFICATION_TTL_SECONDS),
        )
        connection.commit()
    finally:
        connection.close()

    from deploy.adapters.email_adapter import send_email_reply

    subject = "Your Cortex verification code"
    body = (
        f"Your Cortex verification code is: {code}\n\n"
        f"It expires in 10 minutes. Enter it to finish verifying "
        f"{normalized_email} and accept your brain invitation."
    )
    send_email_reply(normalized_email, subject, body)

    return {
        "email": normalized_email,
        "employee_id": str(employee_id).strip(),
        "expires_at": now + VERIFICATION_TTL_SECONDS,
        "sent": True,
    }


def verify_email_code(email: str, code: str) -> bool:
    """Validate a 6-digit code and mark the employee's work email verified.

    Returns True only for an unexpired code issued to that email; the code is
    consumed (deleted) on success, and the matching employee record's
    ``work_email_verified`` flag is set.
    """
    normalized_email = _normalize_email(email)
    normalized_code = str(code).strip()
    if len(normalized_code) != _CODE_DIGITS or not normalized_code.isdigit():
        return False

    connection = connect()
    try:
        row = connection.execute(
            "SELECT employee_id, expires_at FROM email_verifications "
            "WHERE email = ? AND code = ?",
            (normalized_email, normalized_code),
        ).fetchone()
        if row is None:
            return False
        employee_id, expires_at = row
        if expires_at < int(time.time()):
            connection.execute(
                "DELETE FROM email_verifications WHERE email = ? AND code = ?",
                (normalized_email, normalized_code),
            )
            connection.commit()
            return False
        connection.execute(
            "UPDATE employees SET work_email_verified = 1 "
            "WHERE employee_id = ? AND work_email = ?",
            (employee_id, normalized_email),
        )
        connection.execute(
            "DELETE FROM email_verifications WHERE email = ? AND code = ?",
            (normalized_email, normalized_code),
        )
        connection.commit()
        return True
    finally:
        connection.close()
