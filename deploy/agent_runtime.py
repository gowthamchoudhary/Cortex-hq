"""Core agent runtime: the single place inbound platform messages reach reasoning.

Every adapter (Slack, GitHub, email, WhatsApp) reduces an inbound message to
``handle_incoming_message(agent_id, raw_message, platform_user_id, platform)``
and formats the platform-agnostic response it returns. Nothing else in the
deploy stack calls ``reasoning.answer_question`` directly.

Flow:
1. Look up the agent's config (HydraDB collection + default role).
2. Resolve the platform user to a role through the canonical identity layer:
   ``identity.external_identities.resolve_platform_user`` maps the platform
   identity to an ``employee_id``, and the employee's ``cortex_role`` from the
   directory (``identity.employee_directory``) is the role used for answering.
   Unlinked senders fall back to the agent's ``role_default`` (logged clearly).
3. Call ``reasoning.answer_question`` with the resolved role.
4. Return ``{answer, confidence, evidence_doc_ids, abstained}``.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from auth.user_brains import get_user_id_by_identity, get_user_role_in_brain  # noqa: E402
from deploy.agent_manager import get_agent_chat_endpoint  # noqa: E402
from identity.employee_directory import get_employee  # noqa: E402
from identity.external_identities import resolve_platform_user  # noqa: E402
from reasoning.answer_question import answer_question  # noqa: E402

logger = logging.getLogger(__name__)

# Defaults for the reasoning pipeline when an agent config does not override them.
DEFAULT_PROVIDER = "auto"
DEFAULT_MODEL = None
DEFAULT_TIMEOUT_SECONDS = 90


def _resolve_role(
    platform_user_id: str | None,
    endpoint: dict[str, Any],
    platform: str | None = None,
) -> str:
    """Resolve the caller's role from the canonical identity layer.

    With a ``platform`` given, the platform identity is routed through the
    employee directory: platform user -> employee_id -> ``cortex_role``. When
    the sender is unlinked, the agent's ``role_default`` applies and the
    fallback is logged so unknown-sender traffic is visible.

    Without a ``platform`` (legacy callers), the old behavior is preserved:
    the platform id is resolved via ``auth.user_brains`` identities, then the
    user's role in the agent's collection, else the agent default.
    """
    collection = str(endpoint["collection"])
    if platform and platform_user_id:
        try:
            employee_id = resolve_platform_user(collection, platform, str(platform_user_id))
        except ValueError:
            employee_id = None
        if employee_id:
            employee = get_employee(collection, employee_id)
            if employee and employee.get("cortex_role"):
                return str(employee["cortex_role"])
            logger.warning(
                "%s user %r mapped to employee %r in collection %r but the employee "
                "record or role is missing; falling back to agent role_default %r.",
                platform,
                platform_user_id,
                employee_id,
                collection,
                endpoint["role"],
            )
        else:
            logger.warning(
                "Unlinked %s sender %r in collection %r — no employee mapping found; "
                "answering with agent role_default %r.",
                platform,
                platform_user_id,
                collection,
                endpoint["role"],
            )
        return str(endpoint["role"])

    # Legacy path (platform not specified): resolve via auth.user_brains identities.
    if platform_user_id:
        cortex_user_id = get_user_id_by_identity(str(platform_user_id))
        if cortex_user_id:
            mapped_role = get_user_role_in_brain(cortex_user_id, collection)
            if mapped_role:
                return mapped_role
    return str(endpoint["role"])


def handle_incoming_message(
    agent_id: str,
    raw_message: str,
    platform_user_id: str | None,
    platform: str | None = None,
) -> dict[str, Any]:
    """Answer ``raw_message`` as ``agent_id`` and return a platform-agnostic reply.

    ``platform_user_id`` is the platform's own identity for the caller (a Slack
    user id, GitHub username, email address, or WhatsApp phone number) and
    ``platform`` is one of ``slack``/``github``/``email``/``whatsapp``. With a
    platform, the caller's role comes from the employee directory via
    ``identity.external_identities``; unlinked senders get the agent's
    ``role_default`` (logged). Without a platform, the legacy
    ``auth.user_brains`` identity path applies.

    Returns ``{answer, confidence, evidence_doc_ids, abstained}``.
    """
    if not str(raw_message).strip():
        raise ValueError("raw_message must not be empty.")
    endpoint = get_agent_chat_endpoint(agent_id)  # Raises KeyError for unknown agents.
    role = _resolve_role(platform_user_id, endpoint, platform=platform)

    result = answer_question(
        question=str(raw_message).strip(),
        database=endpoint["database"],
        collection=endpoint["collection"],
        provider=DEFAULT_PROVIDER,
        model=DEFAULT_MODEL,
        timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
        verbose=False,
        role=role,
    )
    return {
        "answer": str(result.get("answer") or ""),
        "confidence": float(result.get("confidence") or 0.0),
        "evidence_doc_ids": list(result.get("evidence") or []),
        "abstained": bool(result.get("abstained")),
    }
