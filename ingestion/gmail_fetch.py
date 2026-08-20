"""Fetch Gmail messages live via the Gmail API using an OAuth access token.

The returned records are shaped for ``ingestion.normalize.normalize_gmail``:
each dict has ``thread_id``, ``sender``, ``subject``, ``first_email_at``,
``last_email_at``, and ``messages`` — the same shape that
``parse_gmail_takeout`` produces from local mbox files.

Token refresh is handled externally (``oauth.tokens`` + Flask callback);
this module assumes ``access_token`` is valid.
"""

from __future__ import annotations

import base64
import html
import re
from typing import Any

import httpx

GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1"
DEFAULT_MAX_RESULTS = 100
DEFAULT_TIMEOUT_SECONDS = 30


def fetch_gmail_messages(
    access_token: str,
    *,
    max_results: int = DEFAULT_MAX_RESULTS,
    query: str = "",
) -> list[dict[str, Any]]:
    """Fetch recent Gmail threads and return normalize_gmail-shaped records.

    ``access_token`` must have ``gmail.readonly`` scope.
    ``query`` is an optional Gmail search query (e.g. ``after:2025/01/01``).
    """
    headers = {"Authorization": f"Bearer {access_token}"}
    params: dict[str, Any] = {"maxResults": max_results, "userId": "me"}
    if query:
        params["q"] = query

    with httpx.Client(timeout=DEFAULT_TIMEOUT_SECONDS) as client:
        # List thread IDs
        list_resp = client.get(f"{GMAIL_API_BASE}/users/me/threads", headers=headers, params=params)
        list_resp.raise_for_status()
        threads = list_resp.json().get("threads") or []

        records: list[dict[str, Any]] = []
        for thread_stub in threads:
            thread_id = thread_stub.get("id", "")
            if not thread_id:
                continue
            # Fetch full thread
            thread_resp = client.get(
                f"{GMAIL_API_BASE}/users/me/threads/{thread_id}",
                headers=headers,
                params={"format": "full"},
            )
            thread_resp.raise_for_status()
            thread_data = thread_resp.json()
            record = _parse_thread(thread_id, thread_data)
            if record is not None:
                records.append(record)

    return records


def _parse_thread(thread_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
    """Convert a Gmail thread response into a normalize_gmail-shaped dict."""
    messages = data.get("messages") or []
    if not messages:
        return None

    parsed_msgs: list[dict[str, Any]] = []
    for msg in messages:
        headers_list = msg.get("payload", {}).get("headers") or []
        headers = {h["name"].lower(): h.get("value", "") for h in headers_list if isinstance(h, dict)}
        body = _extract_body(msg.get("payload", {}))
        parsed_msgs.append({
            "message_id": msg.get("id", ""),
            "sender": headers.get("from", ""),
            "date": headers.get("date", ""),
            "subject": headers.get("subject", ""),
            "body": body,
        })

    if not parsed_msgs:
        return None

    # Sort by date (best-effort, string comparison works for ISO-ish dates)
    parsed_msgs.sort(key=lambda m: m.get("date", ""))
    first = parsed_msgs[0]
    last = parsed_msgs[-1]

    return {
        "thread_id": thread_id,
        "sender": first.get("sender", ""),
        "subject": first.get("subject", ""),
        "first_email_at": first.get("date", ""),
        "last_email_at": last.get("date", ""),
        "messages": parsed_msgs,
    }


def _extract_body(payload: dict[str, Any]) -> str:
    """Recursively extract text/plain (or text/html) body from a Gmail payload."""
    mime_type = payload.get("mimeType", "")

    # Leaf node
    if mime_type == "text/plain":
        data = payload.get("data", "")
        if data:
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
        return ""

    if mime_type == "text/html":
        data = payload.get("data", "")
        if data:
            raw = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
            # Strip HTML tags
            text = re.sub(r"<[^>]+>", " ", raw)
            return html.unescape(text).strip()
        return ""

    # Multipart: recurse into parts
    parts = payload.get("parts") or []
    text_parts: list[str] = []
    html_parts: list[str] = []
    for part in parts:
        body = _extract_body(part)
        if not body:
            continue
        if part.get("mimeType") == "text/plain":
            text_parts.append(body)
        elif part.get("mimeType") == "text/html":
            html_parts.append(body)
        else:
            text_parts.append(body)

    if text_parts:
        return "\n\n".join(text_parts)
    if html_parts:
        return "\n\n".join(html_parts)
    return ""
