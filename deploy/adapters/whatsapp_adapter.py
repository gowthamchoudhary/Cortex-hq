"""WhatsApp adapter: Meta WhatsApp Business Cloud API webhook.

We use Meta's official WhatsApp Business Cloud API (not Twilio) — Meta's free
tier allows testing with a test number and up to a handful of conversations,
so there is no per-message cost during development.

SETUP (do once):

1. Create a Meta developer app at https://developers.facebook.com, add the
   WhatsApp product, and connect a business (or use the free test number).
2. Under WhatsApp → API Setup, note:
   - ``WHATSAPP_PHONE_NUMBER_ID`` — the phone-number id for the sender number
   - ``WHATSAPP_ACCESS_TOKEN``    — the temporary/system-user access token
3. Configure the webhook: set the callback URL to
   ``https://<your-public-url>/whatsapp/webhook`` (ngrok for local dev) and a
   verify token of your choice. This adapter answers the ``hub.challenge``
   verification handshake automatically.
4. Subscribe the webhook to the ``messages`` field for your WhatsApp business
   account / phone number.
5. Set env vars:

   - ``WHATSAPP_ACCESS_TOKEN``           — Meta access token
   - ``WHATSAPP_PHONE_NUMBER_ID``        — sender phone-number id
   - ``WHATSAPP_WEBHOOK_VERIFY_TOKEN``   — your chosen webhook verify token
   - ``CORTEX_WHATSAPP_AGENT_ID``        — agent id to answer with (or ``CORTEX_AGENT_ID``)
   - ``HYDRADB_API_KEY`` and an LLM key (``GROQ_API_KEY``/``OPENAI_API_KEY``)

Run the app::

    flask --app deploy/adapters/whatsapp_adapter run --host 0.0.0.0 --port 5000

Phone numbers are matched to Cortex roles through the canonical identity layer
(``identity.external_identities`` -> employee directory, E.164 e.g.
``+15551234567``); unlinked numbers get the agent's default role (logged by the
runtime).
"""

from __future__ import annotations

import os
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

GRAPH_API_BASE = "https://graph.facebook.com"
GRAPH_API_VERSION = "v19.0"


def _agent_id() -> str:
    agent_id = os.environ.get("CORTEX_WHATSAPP_AGENT_ID") or os.environ.get("CORTEX_AGENT_ID")
    if not agent_id:
        raise RuntimeError("CORTEX_WHATSAPP_AGENT_ID (or CORTEX_AGENT_ID) env var is required.")
    return agent_id


def send_whatsapp_reply(to_phone: str, text: str) -> dict[str, Any]:
    """LIVE CALL: send a WhatsApp text message via the Cloud API.

    Only fires when ``WHATSAPP_ACCESS_TOKEN`` and ``WHATSAPP_PHONE_NUMBER_ID``
    are configured. Mock this function in tests.
    """
    token = os.environ.get("WHATSAPP_ACCESS_TOKEN")
    phone_number_id = os.environ.get("WHATSAPP_PHONE_NUMBER_ID")
    if not token or not phone_number_id:
        raise RuntimeError(
            "WHATSAPP_ACCESS_TOKEN and WHATSAPP_PHONE_NUMBER_ID are not configured; "
            "set them to enable live WhatsApp replies."
        )
    response = httpx.post(
        f"{GRAPH_API_BASE}/{GRAPH_API_VERSION}/{phone_number_id}/messages",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={
            "messaging_product": "whatsapp",
            "to": to_phone,
            "type": "text",
            "text": {"body": text},
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def format_whatsapp_reply(result: dict[str, Any]) -> str:
    """Format the runtime response as plain WhatsApp text (1600-char friendly)."""
    lines = [str(result.get("answer") or "")]
    evidence = list(result.get("evidence_doc_ids") or [])
    if evidence:
        lines.append("")
        lines.append("Evidence:")
        lines.extend(f"- {doc_id}" for doc_id in evidence)
    lines.append("")
    lines.append(f"Confidence: {float(result.get('confidence') or 0.0):.0%}")
    if result.get("abstained"):
        lines.append("(Abstained — not enough evidence in the connected data.)")
    return "\n".join(lines)


@app.route("/whatsapp/webhook", methods=["GET"])
def whatsapp_verify() -> Any:
    """Meta webhook verification handshake (hub.challenge)."""
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    expected = os.environ.get("WHATSAPP_WEBHOOK_VERIFY_TOKEN", "")
    if mode == "subscribe" and token and expected and token == expected:
        return challenge or ("", 200)
    return jsonify({"error": "verification failed"}), 403


@app.route("/whatsapp/webhook", methods=["POST"])
def whatsapp_webhook() -> Any:
    """WhatsApp Cloud API webhook: message events only, text messages only."""
    payload = request.get_json(silent=True) or {}
    messages = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            if value.get("messaging_product") != "whatsapp":
                continue
            messages.extend(value.get("messages", []))

    for message in messages:
        if message.get("type") != "text":
            continue
        question = str(message.get("text", {}).get("body") or "").strip()
        sender_phone = str(message.get("from") or "")
        if not question or not sender_phone:
            continue
        try:
            result = handle_incoming_message(
                _agent_id(), question, sender_phone, platform="whatsapp"
            )
            send_whatsapp_reply(sender_phone, format_whatsapp_reply(result))
        except Exception as exc:  # noqa: BLE001 — log and ack; never crash the webhook
            app.logger.exception("WhatsApp handler failed: %s", exc)
            return jsonify({"ok": False, "error": str(exc)}), 500
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
