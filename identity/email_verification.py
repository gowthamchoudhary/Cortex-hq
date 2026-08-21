"""Verified-work-email second factor (lightweight SSO stand-in).

Full enterprise SSO is out of scope for a custom IdP, so Cortex uses the
verified-work-email pattern as its "second factor": a 6-digit code sent to the
employee's work email, valid for 10 minutes. ``accept_invitation`` refuses to
grant access until the employee's work email is verified, which forces invitees
to prove they control the company email address attached to their directory
record.

Codes are stored in Supabase Postgres and sent through the
existing SendGrid setup in ``deploy.adapters.email_adapter`` (``SENDGRID_API_KEY``
+ ``CORTEX_EMAIL_FROM`` required at send time).
"""

from __future__ import annotations

import os
import random
import time
from typing import Any

from identity._store import get_client, EMPLOYEES, EMAIL_VERIFICATIONS
from identity.employee_directory import get_employee

VERIFICATION_TTL_SECONDS = 10 * 60  # 10 minutes
_CODE_DIGITS = 6


def _normalize_email(email: str) -> str:
    return str(email).strip().lower()


def _find_employee_by_email_and_id(email: str, employee_id: str) -> dict[str, Any] | None:
    """Locate the employee across collections matching (employee_id, work_email)."""
    client = get_client()
    result = (
        client.table(EMPLOYEES)
        .select("collection")
        .eq("employee_id", str(employee_id).strip())
        .eq("work_email", _normalize_email(email))
        .limit(1)
        .execute()
    )
    if not result.data:
        return None
    return get_employee(result.data[0]["collection"], str(employee_id).strip())


def send_verification_email(email: str, employee_id: str) -> dict[str, Any]:
    """Generate a 6-digit code, store it with a 10-minute expiry, and email it."""
    normalized_email = _normalize_email(email)
    employee = _find_employee_by_email_and_id(normalized_email, employee_id)
    if employee is None:
        raise ValueError(
            f"No employee matches employee_id {employee_id!r} with work_email {email!r}."
        )

    code = "".join(str(random.SystemRandom().randrange(10)) for _ in range(_CODE_DIGITS))
    now = int(time.time())

    client = get_client()
    client.table(EMAIL_VERIFICATIONS).upsert({
        "email": normalized_email,
        "code": code,
        "employee_id": str(employee_id).strip(),
        "created_at": now,
        "expires_at": now + VERIFICATION_TTL_SECONDS,
    }, on_conflict="email,code").execute()

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
    """Validate a 6-digit code and mark the employee's work email verified."""
    normalized_email = _normalize_email(email)
    normalized_code = str(code).strip()
    if len(normalized_code) != _CODE_DIGITS or not normalized_code.isdigit():
        return False

    client = get_client()
    result = (
        client.table(EMAIL_VERIFICATIONS)
        .select("employee_id,expires_at")
        .eq("email", normalized_email)
        .eq("code", normalized_code)
        .limit(1)
        .execute()
    )
    if not result.data:
        return False

    row = result.data[0]
    employee_id = row["employee_id"]
    expires_at = row["expires_at"]

    if expires_at < int(time.time()):
        client.table(EMAIL_VERIFICATIONS).delete().eq(
            "email", normalized_email
        ).eq("code", normalized_code).execute()
        return False

    # Mark employee's email as verified
    client.table(EMPLOYEES).update(
        {"work_email_verified": 1}
    ).eq("employee_id", employee_id).eq("work_email", normalized_email).execute()

    # Delete the used code
    client.table(EMAIL_VERIFICATIONS).delete().eq(
        "email", normalized_email
    ).eq("code", normalized_code).execute()

    return True
