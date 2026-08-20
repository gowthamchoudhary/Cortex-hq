"""Fetch Slack messages live via the Slack Web API using an OAuth access token.

The returned records are shaped for ``ingestion.normalize.normalize_slack``:
each dict has ``message_id``, ``channel``, ``channel_id``, ``user_name``,
``timestamp``, and ``text`` — the same shape that ``parse_slack_export``
produces from local export directories.

Token refresh is handled externally (``oauth.tokens`` + Flask callback);
this module assumes ``access_token`` is valid.
"""

from __future__ import annotations

import re
import time
from typing import Any

import httpx

SLACK_API_BASE = "https://slack.com/api"
DEFAULT_MAX_MESSAGES = 200
DEFAULT_TIMEOUT_SECONDS = 30


def fetch_slack_messages(
    access_token: str,
    *,
    max_messages: int = DEFAULT_MAX_MESSAGES,
    channel_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Fetch recent Slack messages and return normalize_slack-shaped records.

    ``access_token`` must have ``channels:history``, ``channels:read``,
    and ``users:read`` scopes.
    ``channel_ids`` is an optional list; if omitted, all accessible channels
    are fetched.
    """
    headers = {"Authorization": f"Bearer {access_token}"}

    with httpx.Client(timeout=DEFAULT_TIMEOUT_SECONDS) as client:
        # Resolve user IDs to display names
        users = _fetch_users(client, headers)

        # Get channel list
        if channel_ids:
            channels = [{"id": cid, "name": cid} for cid in channel_ids]
        else:
            channels = _fetch_channels(client, headers)

        records: list[dict[str, Any]] = []
        for ch in channels:
            ch_id = ch.get("id", "")
            ch_name = ch.get("name", ch_id)
            if not ch_id:
                continue
            messages = _fetch_channel_history(client, headers, ch_id, max_messages)
            for msg in messages:
                record = _parse_message(msg, ch_name, ch_id, users)
                if record is not None:
                    records.append(record)

    return records


def _fetch_users(client: httpx.Client, headers: dict[str, str]) -> dict[str, str]:
    """Return a mapping of user_id -> display_name."""
    users: dict[str, str] = {}
    cursor = ""
    while True:
        params: dict[str, Any] = {"limit": 200}
        if cursor:
            params["cursor"] = cursor
        resp = client.get(f"{SLACK_API_BASE}/users.list", headers=headers, params=params)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            break
        for member in data.get("members") or []:
            uid = member.get("id", "")
            profile = member.get("profile") or {}
            name = (
                profile.get("display_name")
                or profile.get("real_name")
                or member.get("name", "")
            )
            if uid and name:
                users[uid] = name
        cursor = (data.get("response_metadata") or {}).get("next_cursor", "")
        if not cursor:
            break
    return users


def _fetch_channels(client: httpx.Client, headers: dict[str, str]) -> list[dict[str, Any]]:
    """Return list of channels with id and name."""
    channels: list[dict[str, Any]] = []
    cursor = ""
    while True:
        params: dict[str, Any] = {"limit": 200, "types": "public_channel,private_channel"}
        if cursor:
            params["cursor"] = cursor
        resp = client.get(f"{SLACK_API_BASE}/conversations.list", headers=headers, params=params)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            break
        for ch in data.get("channels") or []:
            channels.append({"id": ch.get("id", ""), "name": ch.get("name", "")})
        cursor = (data.get("response_metadata") or {}).get("next_cursor", "")
        if not cursor:
            break
    return channels


def _fetch_channel_history(
    client: httpx.Client,
    headers: dict[str, str],
    channel_id: str,
    max_messages: int,
) -> list[dict[str, Any]]:
    """Fetch up to ``max_messages`` messages from a channel."""
    messages: list[dict[str, Any]] = []
    cursor = ""
    remaining = max_messages
    while remaining > 0:
        params: dict[str, Any] = {"limit": min(remaining, 200)}
        if cursor:
            params["cursor"] = cursor
        resp = client.get(
            f"{SLACK_API_BASE}/conversations.history",
            headers=headers,
            params={**params, "channel": channel_id},
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            break
        batch = data.get("messages") or []
        messages.extend(batch)
        remaining -= len(batch)
        has_more = data.get("has_more", False)
        cursor = (data.get("response_metadata") or {}).get("next_cursor", "")
        if not has_more or not cursor:
            break
        # Respect Slack rate limits
        time.sleep(0.5)
    return messages


def _parse_message(
    msg: dict[str, Any],
    channel_name: str,
    channel_id: str,
    users: dict[str, str],
) -> dict[str, Any] | None:
    """Convert a Slack message into a normalize_slack-shaped dict."""
    text = str(msg.get("text") or "").strip()
    if not text:
        return None

    user_id = str(msg.get("user") or msg.get("bot_id") or msg.get("username") or "")
    user_name = users.get(user_id, user_id)

    # Resolve <@U123> mentions
    resolved_text = _resolve_mentions(text, users)

    ts = str(msg.get("ts") or "")
    record: dict[str, Any] = {
        "message_id": ts,
        "channel": channel_name,
        "channel_id": channel_id,
        "user": user_id,
        "user_name": user_name,
        "timestamp": ts,
        "text": resolved_text,
    }
    if msg.get("thread_ts"):
        record["thread_ts"] = str(msg["thread_ts"])
    if msg.get("subtype"):
        record["subtype"] = str(msg["subtype"])
    if isinstance(msg.get("replies"), list):
        record["reply_count"] = len(msg["replies"])
    return record


def _resolve_mentions(text: str, users: dict[str, str]) -> str:
    """Replace <@U123> mentions with display names."""
    def replace(match: re.Match[str]) -> str:
        user_id = match.group(1)
        return f"@{users[user_id]}" if user_id in users else match.group(0)
    return re.sub(r"<@([A-Z0-9]+)>", replace, text)
