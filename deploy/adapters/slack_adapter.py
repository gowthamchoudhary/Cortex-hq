"""Slack adapter: receives Slack Events API payloads and replies via chat.postMessage.

SETUP (do once, per workspace):

1. Create a Slack app at https://api.slack.com/apps.
2. Bot Token Scopes: ``chat:write`` (post replies) and ``app_mentions:read``
   (receive mentions). Install the app to your workspace and copy the
   ``xoxb-...`` Bot User OAuth Token.
3. Event Subscriptions → enable, set Request URL to
   ``https://<your-public-url>/slack/events``. This URL must be publicly
   reachable — ngrok for local dev (``ngrok http 5000``) or wherever this gets
   hosted. Slack sends a URL-verification ``challenge`` that this endpoint
   answers automatically.
4. Subscribe to bot events: ``app_mention`` (and ``message.im`` if you want
   DMs to the bot).
5. Set env vars:

   - ``SLACK_BOT_TOKEN``          — the xoxb bot token (chat:write)
   - ``CORTEX_SLACK_AGENT_ID``    — agent id to answer with (or ``CORTEX_AGENT_ID``)
   - ``HYDRADB_API_KEY``          — required by the reasoning pipeline
   - ``GROQ_API_KEY`` / ``OPENAI_API_KEY`` — LLM provider key for answering

Run the app::

    flask --app deploy/adapters/slack_adapter run --host 0.0.0.0 --port 5000

Users are matched to Cortex roles by their Slack user id through
``auth.user_brains`` identities; unregistered users get the agent's default role.
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


def _agent_id() -> str:
    agent_id = os.environ.get("CORTEX_SLACK_AGENT_ID") or os.environ.get("CORTEX_AGENT_ID")
    if not agent_id:
        raise RuntimeError("CORTEX_SLACK_AGENT_ID (or CORTEX_AGENT_ID) env var is required.")
    return agent_id


def _strip_mention(text: str) -> str:
    """Remove Slack user/bot mentions (<@U123>, <@U123|name>) from question text."""
    return re.sub(r"<@[A-Z0-9]+(?:\|[^>]*)?>", "", text or "").strip()


def post_slack_message(channel: str, text: str) -> dict[str, Any]:
    """LIVE CALL: post ``text`` to a Slack channel via chat.postMessage.

    Only fires when ``SLACK_BOT_TOKEN`` is set. Mock this function in tests.
    """
    token = os.environ.get("SLACK_BOT_TOKEN")
    if not token:
        raise RuntimeError(
            "SLACK_BOT_TOKEN is not configured; set it to enable live Slack replies."
        )
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
    try:
        result = handle_incoming_message(_agent_id(), question, user)
        # Ack Slack fast (3s limit); a synchronous post is fine for a single bot.
        post_slack_message(channel, format_slack_reply(result))
    except Exception as exc:  # noqa: BLE001 — log and ack; never crash the webhook
        app.logger.exception("Slack handler failed: %s", exc)
        return jsonify({"ok": True}), 500
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
