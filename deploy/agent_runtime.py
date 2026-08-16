"""Core agent runtime: the single place inbound platform messages reach reasoning.

Every adapter (Slack, GitHub, email, WhatsApp) reduces an inbound message to
``handle_incoming_message(agent_id, raw_message, platform_user_id)`` and formats
the platform-agnostic response it returns. Nothing else in the deploy stack
calls ``reasoning.answer_question`` directly.

Flow:
1. Look up the agent's config (HydraDB collection + default role).
2. Resolve the platform user to a role: if the platform user id maps to a
   Cortex ``user_id`` via ``auth.user_brains`` identities, use that user's role
   in the agent's collection; otherwise fall back to the agent's ``role_default``.
3. Call ``reasoning.answer_question`` with the resolved role.
4. Return ``{answer, confidence, evidence_doc_ids, abstained}``.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from auth.user_brains import get_user_id_by_identity, get_user_role_in_brain  # noqa: E402
from deploy.agent_manager import get_agent_chat_endpoint  # noqa: E402
from reasoning.answer_question import answer_question  # noqa: E402

# Defaults for the reasoning pipeline when an agent config does not override them.
DEFAULT_PROVIDER = "auto"
DEFAULT_MODEL = None
DEFAULT_TIMEOUT_SECONDS = 90


def _resolve_role(platform_user_id: str | None, endpoint: dict[str, Any]) -> str:
    """Resolve the caller's role from platform identity, else the agent default."""
    if platform_user_id:
        cortex_user_id = get_user_id_by_identity(str(platform_user_id))
        if cortex_user_id:
            mapped_role = get_user_role_in_brain(cortex_user_id, endpoint["collection"])
            if mapped_role:
                return mapped_role
    return str(endpoint["role"])


def handle_incoming_message(
    agent_id: str,
    raw_message: str,
    platform_user_id: str | None,
) -> dict[str, Any]:
    """Answer ``raw_message`` as ``agent_id`` and return a platform-agnostic reply.

    ``platform_user_id`` is the platform's own identity for the caller (a Slack
    user id, GitHub username, email address, or WhatsApp phone number). When it
    maps to a Cortex user via ``auth.user_brains``, the mapped role is used;
    otherwise the agent's ``role_default`` applies.

    Returns ``{answer, confidence, evidence_doc_ids, abstained}``.
    """
    if not str(raw_message).strip():
        raise ValueError("raw_message must not be empty.")
    endpoint = get_agent_chat_endpoint(agent_id)  # Raises KeyError for unknown agents.
    role = _resolve_role(platform_user_id, endpoint)

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
