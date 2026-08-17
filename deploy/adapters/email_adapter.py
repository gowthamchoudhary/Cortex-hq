"""Email adapter: answers questions received by inbound email webhook.

PROVIDER CHOICE — SendGrid Inbound Parse.

Both SendGrid Inbound Parse and Mailgun Routes need a receiving domain with MX
records and a public webhook URL. We pick **SendGrid** because the free tier
includes inbound parse on one subdomain and the webhook is a plain multipart
POST containing the raw email — no routing-rule DSL to learn. Sending uses the
same provider's v3 Mail Send API.

SETUP (do once):

1. Create a SendGrid account (free tier is fine).
2. Inbound Parse (Settings → Inbound Parse): add a subdomain (e.g.
   ``inbound.yourdomain.com``), set the URL to
   ``https://<your-public-url>/email/webhook`` (ngrok for local dev), and
   select "Post the raw, full MIME message" so ``process_inbound_email`` gets
   the complete raw bytes.
3. Add the required MX record on ``inbound.yourdomain.com`` pointing at
   ``mx.sendgrid.net`` (SendGrid's docs list the exact record).
4. Generate an API key (Settings → API Keys) with "Mail Send" scope.
5. Set env vars:

   - ``SENDGRID_API_KEY``         — API key with Mail Send scope
   - ``CORTEX_EMAIL_AGENT_ID``    — agent id to answer with (or ``CORTEX_AGENT_ID``)
   - ``CORTEX_EMAIL_FROM``        — verified sender address the reply comes from
   - ``HYDRADB_API_KEY`` and an LLM key (``GROQ_API_KEY``/``OPENAI_API_KEY``)

Wire the webhook (the receiving side is hosted by SendGrid; the URL it posts to
is served by this Flask app)::

    flask --app deploy/adapters/email_adapter run --host 0.0.0.0 --port 5000

Sender addresses are matched to Cortex roles through the canonical identity
layer (``identity.external_identities`` -> employee directory); unlinked
senders get the agent's default role (logged by the runtime).
"""

from __future__ import annotations

import email
import os
import re
import sys
from email.header import decode_header, make_header
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
    agent_id = os.environ.get("CORTEX_EMAIL_AGENT_ID") or os.environ.get("CORTEX_AGENT_ID")
    if not agent_id:
        raise RuntimeError("CORTEX_EMAIL_AGENT_ID (or CORTEX_AGENT_ID) env var is required.")
    return agent_id


def _decode_header_value(value: str | None) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except (TypeError, ValueError, email.errors.HeaderParseError):
        return str(value)


def _sender_address(raw_message: email.message.Message) -> str:
    """Return the From address, or empty when unparseable."""
    from_header = _decode_header_value(raw_message.get("From", ""))
    match = re.search(r"[^@\s<>]+@[^@\s<>]+", from_header)
    return match.group(0).lower() if match else ""


def _body_text(raw_message: email.message.Message) -> str:
    """Extract plain-text body; fall back to stripped HTML."""
    if raw_message.is_multipart():
        for part in raw_message.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain":
                payload = part.get_payload(decode=True)
                if payload is not None:
                    charset = part.get_content_charset() or "utf-8"
                    try:
                        return payload.decode(charset, errors="replace").strip()
                    except (LookupError, UnicodeDecodeError):
                        return payload.decode("utf-8", errors="replace").strip()
        for part in raw_message.walk():
            if part.get_content_type() == "text/html":
                payload = part.get_payload(decode=True)
                if payload is not None:
                    charset = part.get_content_charset() or "utf-8"
                    try:
                        html = payload.decode(charset, errors="replace")
                    except (LookupError, UnicodeDecodeError):
                        html = payload.decode("utf-8", errors="replace")
                    return re.sub(r"<[^>]+>", " ", html).strip()
        return ""
    payload = raw_message.get_payload(decode=True)
    if payload is None:
        return ""
    charset = raw_message.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace").strip()
    except (LookupError, UnicodeDecodeError):
        return payload.decode("utf-8", errors="replace").strip()


def parse_inbound_email(raw_email_bytes: bytes) -> dict[str, str]:
    """Parse raw MIME bytes into ``{sender, subject, body}``."""
    message = email.message_from_bytes(raw_email_bytes)
    subject = _decode_header_value(message.get("Subject", ""))
    return {
        "sender": _sender_address(message),
        "subject": subject,
        "body": _body_text(message),
    }


def send_email_reply(to_email: str, subject: str, body: str) -> dict[str, Any]:
    """LIVE CALL: send a reply email via SendGrid's v3 Mail Send API.

    Only fires when ``SENDGRID_API_KEY`` is set. Mock this function in tests.
    """
    api_key = os.environ.get("SENDGRID_API_KEY")
    if not api_key:
        raise RuntimeError(
            "SENDGRID_API_KEY is not configured; set it to enable live email replies."
        )
    from_address = os.environ.get("CORTEX_EMAIL_FROM")
    if not from_address:
        raise RuntimeError("CORTEX_EMAIL_FROM env var is required for replies.")
    response = httpx.post(
        "https://api.sendgrid.com/v3/mail/send",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "personalizations": [{"to": [{"email": to_email}]}],
            "from": {"email": from_address},
            "subject": subject,
            "content": [{"type": "text/plain", "value": body}],
        },
        timeout=30,
    )
    response.raise_for_status()
    return {"status_code": response.status_code}


def format_email_reply(result: dict[str, Any]) -> tuple[str, str]:
    """Return ``(subject, body)`` for the reply email."""
    subject = "Re: your Cortex question"
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
    return subject, "\n".join(lines)


def process_inbound_email(raw_email_bytes: bytes) -> dict[str, Any]:
    """Handle one inbound email: parse, answer, and reply.

    Designed to be called from the inbound-email webhook endpoint below (or any
    provider webhook that forwards raw MIME bytes). Returns the runtime result
    plus the sender the reply was addressed to.
    """
    parsed = parse_inbound_email(raw_email_bytes)
    sender = parsed["sender"]
    question = f"{parsed['subject']}\n{parsed['body']}".strip()
    if not sender:
        raise ValueError("Inbound email has no usable From address.")
    if not question:
        raise ValueError("Inbound email has no subject or body to answer.")

    result = handle_incoming_message(_agent_id(), question, sender, platform="email")
    subject, body = format_email_reply(result)
    send_email_reply(sender, subject, body)
    return {**result, "reply_to": sender}


@app.route("/email/webhook", methods=["POST"])
def email_webhook() -> Any:
    """SendGrid Inbound Parse webhook: multipart form with the raw MIME email.

    SendGrid posts ``email`` (the raw message) plus headers/text fields; we
    prefer the raw MIME field so parsing is exact.
    """
    raw_email = request.form.get("email", "")
    if not raw_email:
        # Some providers post a ``message`` field or the raw body instead.
        raw_email = request.form.get("message", "") or request.get_data(as_text=True)
    if not raw_email:
        return jsonify({"ok": False, "error": "no email payload"}), 400
    try:
        result = process_inbound_email(raw_email.encode("utf-8", errors="replace"))
    except Exception as exc:  # noqa: BLE001 — log and ack; never crash the webhook
        app.logger.exception("Email handler failed: %s", exc)
        return jsonify({"ok": False, "error": str(exc)}), 500
    return jsonify({"ok": True, "reply_to": result.get("reply_to")})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
