"""Slack adapter: receives Slack Events API payloads and replies via chat.postMessage.

Multi-tenant support
--------------------
Each organization (Cortex "brain" / collection) installs the Slack app to
their own workspace.  The adapter looks up the correct bot token for the
incoming event's ``team_id`` via ``oauth.tokens.get_bot_token_for_team``.

Fallback: if no stored bot token is found, the adapter falls back to
``SLACK_BOT_TOKEN`` env var for backward compatibility with single-workspace
deployments.

SETUP (do once, per workspace):

1. Create a Slack app at https://api.slack.com/apps.
2. Bot Token Scopes: ``chat:write`` (post replies), ``app_mentions:read``
   (receive mentions), ``channels:history``, ``channels:read``, ``users:read``.
3. Install the app to your workspace — the bot token (``xoxb-…``) is stored
   automatically via the Cortex OAuth flow.
4. Event Subscriptions → enable, set Request URL to
   ``https://<your-public-url>/slack/events``.
5. Subscribe to bot events: ``app_mention`` (and ``message.im`` for DMs).

For single-workspace deployments, set env vars:

   - ``SLACK_BOT_TOKEN``          — the xoxb bot token (chat:write)
   - ``CORTEX_SLACK_AGENT_ID``    — agent id to answer with (or ``CORTEX_AGENT_ID``)
   - ``HYDRADB_API_KEY``          — required by the reasoning pipeline
   - ``GROQ_API_KEY`` / ``OPENAI_API_KEY`` — LLM provider key for answering

Run the app::

    flask --app deploy/adapters.slack_adapter run --host 0.0.0.0 --port 5000

Users are matched to Cortex roles by their Slack user id through the canonical
identity layer (``identity.external_identities`` -> employee directory);
unlinked senders get the agent's default role (logged by the runtime).
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import httpx
from flask import Flask, jsonify, request

from deploy.agent_runtime import handle_incoming_message

app = Flask(__name__)


# ---------------------------------------------------------------------------
# Agent ID resolution
# ---------------------------------------------------------------------------


def _default_agent_id() -> str | None:
    """Return the single-agent env-var override, or None."""
    return os.environ.get("CORTEX_SLACK_AGENT_ID") or os.environ.get("CORTEX_AGENT_ID")


def _agent_id_for_team(team_id: str) -> str | None:
    """Look up the agent deployed to Slack for the given team's collection.

    Returns the first agent whose collection has a stored bot token with
    this ``team_id`` in its metadata, or None.
    """
    try:
        from oauth.tokens import get_bot_token_for_team
        token_info = get_bot_token_for_team(team_id, "slack")
        if not token_info:
            return None
        collection = token_info.get("collection", "")
        if not collection:
            return None
        from deploy.agent_manager import list_agents
        for agent in list_agents():
            if agent.get("collection") == collection:
                # Check that Slack is a deployed platform for this agent.
                for deployment in agent.get("deployments") or []:
                    if deployment.get("platform") == "slack":
                        return agent["agent_id"]
    except Exception:  # noqa: BLE001
        pass
    return None


def _resolve_agent_id(team_id: str | None) -> str:
    """Resolve the agent id to answer with.

    Priority: per-collection lookup (multi-tenant) → env var fallback.
    """
    if team_id:
        resolved = _agent_id_for_team(team_id)
        if resolved:
            return resolved
    # Fallback to single-agent env var.
    agent_id = _default_agent_id()
    if not agent_id:
        raise RuntimeError(
            "No agent found for this Slack workspace and CORTEX_SLACK_AGENT_ID is not set. "
            "Deploy an agent to Slack for this collection, or set CORTEX_SLACK_AGENT_ID."
        )
    return agent_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _strip_mention(text: str) -> str:
    """Remove Slack user/bot mentions (<@U123>, <@U123|name>) from question text."""
    return re.sub(r"@[A-Z0-9]+(?:\\|[^>]*)?>", "", text or "").strip()


def _lookup_bot_token(team_id: str | None) -> str:
    """Return the bot token for the given team, or fall back to env var.

    Priority: OAuth store (multi-tenant) → SLACK_BOT_TOKEN env var.
    """
    if team_id:
        try:
            from oauth.tokens import get_bot_token_for_team
            token_info = get_bot_token_for_team(team_id, "slack")
            if token_info and token_info.get("access_token"):
                return token_info["access_token"]
        except Exception:  # noqa: BLE001
            pass
    # Fallback to legacy env var.
    token = os.environ.get("SLACK_BOT_TOKEN")
    if not token:
        raise RuntimeError(
            "No Slack bot token found for this workspace and SLACK_BOT_TOKEN is not set. "
            "Install the Slack app via OAuth or set SLACK_BOT_TOKEN."
        )
    return token


def post_slack_message(channel: str, text: str, team_id: str | None = None) -> dict[str, Any]:
    """Post ``text`` to a Slack channel via chat.postMessage.

    Uses the per-collection bot token when available (multi-tenant);
    falls back to ``SLACK_BOT_TOKEN`` env var for single-workspace setups.
    """
    token = _lookup_bot_token(team_id)
    response = httpx.post(
        "https://slack.com/api/chat.postMessage",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={"channel": channel, "text": text},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("ok"):
        raise RuntimeError(f"Slack API error: {payload.get('error')}")
    return payload


def format_slack_reply(result: dict[str, Any]) -> str:
    """Format the runtime response as a Slack message (plain text)."""
    lines = [str(result.get("answer") or "")]
    evidence = list(result.get("evidence_doc_ids") or [])
    if evidence:
        lines.append("\n*Evidence:*")
        lines.extend(f"• {doc_id}" for doc_id in evidence)
    lines.append(f"\n*Confidence:* {float(result.get('confidence') or 0.0):.0%}")
    if result.get("abstained"):
        lines.append("_(I abstained — not enough evidence in the connected data.)_")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Flask routes
# ---------------------------------------------------------------------------


@app.route("/slack/events", methods=["POST"])
def slack_events() -> Any:
    """Slack Events API endpoint (URL verification + event callbacks)."""
    payload = request.get_json(silent=True) or {}

    # URL verification handshake — Slack expects the challenge echoed verbatim.
    if payload.get("type") == "url_verification":
        return jsonify({"challenge": payload.get("challenge", "")})

    if payload.get("type") != "event_callback":
        return jsonify({"ok": True})

    event = payload.get("event") or {}
    event_type = event.get("type")

    # We handle app_mention and message events that are not from the bot itself.
    if event_type not in ("app_mention", "message") or event.get("bot_id"):
        return jsonify({"ok": True})

    question = _strip_mention(event.get("text") or "")
    if not question:
        return jsonify({"ok": True})

    channel = event.get("channel")
    user = event.get("user")
    team_id = payload.get("team_id") or event.get("team") or ""

    try:
        agent_id = _resolve_agent_id(team_id)
        result = handle_incoming_message(agent_id, question, user, platform="slack")
        # Ack Slack fast (3s limit); a synchronous post is fine for a single bot.
        post_slack_message(channel, format_slack_reply(result), team_id=team_id)
    except Exception as exc:  # noqa: BLE001 — log and ack; never crash the webhook
        app.logger.exception("Slack handler failed: %s", exc)
        return jsonify({"ok": True}), 500
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
