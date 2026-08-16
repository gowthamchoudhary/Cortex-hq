"""GitHub adapter: answers @-mentions in issue and discussion comments.

SETUP (do once):

1. Create a GitHub App (or fine-grained PAT) for the bot with:
   - ``Issues: read & write``   (issue_comment events + replying)
   - ``Discussions: read & write`` (discussion_comment events + replying)
   Copy the token (``ghp_``/``github_pat_``) into ``GITHUB_BOT_TOKEN``.
2. Register the webhook on your repo (Settings → Webhooks → Add webhook):
   - Payload URL: ``https://<your-public-url>/github/webhook``
     (ngrok for local dev, or wherever this gets hosted)
   - Content type: ``application/json``
   - Events: select ``Issue comments`` and ``Discussions``
3. Set env vars:

   - ``GITHUB_BOT_TOKEN``        — bot token (repo + discussions write scope)
   - ``GITHUB_BOT_USERNAME``     — the bot's GitHub username; only comments
                                   @-mentioning it trigger an answer
   - ``CORTEX_GITHUB_AGENT_ID``  — agent id to answer with (or ``CORTEX_AGENT_ID``)
   - ``HYDRADB_API_KEY`` and an LLM key (``GROQ_API_KEY``/``OPENAI_API_KEY``)

Run the app::

    flask --app deploy/adapters/github_adapter run --host 0.0.0.0 --port 5000

Security note: GitHub can sign webhook payloads with HMAC-SHA256 (secret
configured on the webhook). Verify ``X-Hub-Signature-256`` before trusting the
payload in production — this adapter intentionally keeps verification out of
the minimal path.
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
    agent_id = os.environ.get("CORTEX_GITHUB_AGENT_ID") or os.environ.get("CORTEX_AGENT_ID")
    if not agent_id:
        raise RuntimeError("CORTEX_GITHUB_AGENT_ID (or CORTEX_AGENT_ID) env var is required.")
    return agent_id


def _strip_mention(body: str, username: str) -> str:
    """Remove the bot @-mention, e.g. ``@cortex-bot`` / ``@cortex-bot !``."""
    pattern = rf"@\s*{re.escape(username)}"
    return re.sub(pattern, "", body or "", flags=re.IGNORECASE).strip()


def post_github_reply(
    repo_full_name: str,
    comment_kind: str,
    thread_number: int,
    body: str,
) -> dict[str, Any]:
    """LIVE CALL: post a reply comment via GitHub's REST API.

    ``comment_kind`` is ``issue`` or ``discussion``. Only fires when
    ``GITHUB_BOT_TOKEN`` is set. Mock this function in tests.
    """
    token = os.environ.get("GITHUB_BOT_TOKEN")
    if not token:
        raise RuntimeError(
            "GITHUB_BOT_TOKEN is not configured; set it to enable live GitHub replies."
        )
    endpoint = (
        f"https://api.github.com/repos/{repo_full_name}/issues/{thread_number}/comments"
        if comment_kind == "issue"
        else f"https://api.github.com/repos/{repo_full_name}/discussions/{thread_number}/comments"
    )
    response = httpx.post(
        endpoint,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        json={"body": body},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def format_github_reply(result: dict[str, Any], comment_url: str | None = None) -> str:
    """Format the runtime response as a GitHub markdown reply."""
    lines = [str(result.get("answer") or "")]
    evidence = list(result.get("evidence_doc_ids") or [])
    if evidence:
        lines.append("")
        lines.append("<details>")
        lines.append("<summary>Evidence</summary>")
        lines.append("")
        if comment_url:
            lines.append(f"- [Evidence in context]({comment_url})")
        lines.extend(f"- {doc_id}" for doc_id in evidence)
        lines.append("</details>")
    lines.append("")
    lines.append(f"**Confidence:** {float(result.get('confidence') or 0.0):.0%}")
    if result.get("abstained"):
        lines.append("_(Abstained — not enough evidence in the connected data.)_")
    return "\n".join(lines)


@app.route("/github/webhook", methods=["POST"])
def github_webhook() -> Any:
    """GitHub webhook endpoint for discussion_comment and issue_comment events."""
    event = request.headers.get("X-GitHub-Event", "")
    if event not in ("discussion_comment", "issue_comment"):
        return jsonify({"ok": True, "ignored": f"unhandled event {event}"})

    payload = request.get_json(silent=True) or {}
    bot_username = os.environ.get("GITHUB_BOT_USERNAME", "").strip()
    body = str(payload.get("comment", {}).get("body") or "")

    # Trigger only on @-mentions of the bot; without a configured username
    # there is nothing to match, so ignore the comment entirely.
    if not bot_username:
        return jsonify({"ok": True, "ignored": "bot username not configured"})
    mention_pattern = rf"@\s*{re.escape(bot_username)}"
    if not re.search(mention_pattern, body, flags=re.IGNORECASE):
        return jsonify({"ok": True, "ignored": "no bot mention"})

    commenter = str(payload.get("comment", {}).get("user", {}).get("login") or "")
    repo = str(payload.get("repository", {}).get("full_name") or "")

    if event == "issue_comment":
        thread_number = int(payload.get("issue", {}).get("number") or 0)
        comment_kind = "issue"
        thread_url = str(payload.get("issue", {}).get("html_url") or "")
    else:
        thread_number = int(payload.get("discussion", {}).get("number") or 0)
        comment_kind = "discussion"
        thread_url = str(payload.get("discussion", {}).get("html_url") or "")

    if not repo or not thread_number:
        return jsonify({"ok": True, "ignored": "missing repo/thread identifiers"})

    question = _strip_mention(body, bot_username) if bot_username else body.strip()
    if not question:
        return jsonify({"ok": True, "ignored": "empty question"})

    try:
        result = handle_incoming_message(_agent_id(), question, commenter or None)
        reply = format_github_reply(result, thread_url)
        post_github_reply(repo, comment_kind, thread_number, reply)
    except Exception as exc:  # noqa: BLE001 — log and ack; never crash the webhook
        app.logger.exception("GitHub handler failed: %s", exc)
        return jsonify({"ok": False, "error": str(exc)}), 500
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
