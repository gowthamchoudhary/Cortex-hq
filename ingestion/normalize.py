"""Normalize records into a shared RawDocument shape.

Includes adapters for the EnterpriseRAG-Bench record formats plus parsers for
real-world export formats (Google Takeout Gmail mbox and Slack workspace
exports) that feed those same adapters.
"""

from __future__ import annotations

import argparse
import json
import mailbox
import re
from dataclasses import asdict, dataclass, field
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Callable


@dataclass
class RawDocument:
    source: str
    source_id: str
    author: str
    timestamp: str
    content: str
    container_id: str
    metadata: dict[str, Any] = field(default_factory=dict)


def _first(raw: dict[str, Any], *keys: str, default: str = "") -> Any:
    for key in keys:
        value = raw.get(key)
        if value not in (None, ""):
            return value
    return default


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n\n".join(_stringify(item) for item in value if item not in (None, ""))
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def _content_from_declared_fields(raw: dict[str, Any], fallback_keys: tuple[str, ...]) -> str:
    field_names = raw.get("content_field_names")
    if isinstance(field_names, list):
        parts = [_stringify(raw.get(name)) for name in field_names if raw.get(name) not in (None, "")]
        if parts:
            return "\n\n".join(parts)

    for key in fallback_keys:
        value = raw.get(key)
        if value not in (None, ""):
            return _stringify(value)
    return ""


def _metadata_without(raw: dict[str, Any], excluded: set[str]) -> dict[str, Any]:
    return {key: value for key, value in raw.items() if key not in excluded}


def normalize_slack(raw_json: dict[str, Any]) -> RawDocument:
    source_id = _first(raw_json, "message_id", "ts", "timestamp_id", "id", "dataset_doc_uuid")
    channel = _first(raw_json, "channel_id", "channel", "channel_name", "conversation_id")
    author = _first(raw_json, "user_name", "user", "author", "sender", "from")
    timestamp = _first(raw_json, "timestamp", "ts", "created_at", "datetime", "date")
    content = _content_from_declared_fields(
        raw_json,
        ("text", "message", "content", "body", "description"),
    )

    excluded = {
        "message_id",
        "ts",
        "timestamp_id",
        "id",
        "dataset_doc_uuid",
        "channel_id",
        "channel",
        "channel_name",
        "conversation_id",
        "user_name",
        "user",
        "author",
        "sender",
        "from",
        "timestamp",
        "created_at",
        "datetime",
        "date",
        "text",
        "message",
        "content",
        "body",
        "description",
    }
    return RawDocument(
        source="slack",
        source_id=str(source_id),
        author=str(author),
        timestamp=str(timestamp),
        content=content,
        container_id=str(channel),
        metadata=_metadata_without(raw_json, excluded),
    )


def normalize_jira(raw_json: dict[str, Any]) -> RawDocument:
    source_id = _first(raw_json, "issue_key", "key", "ticket_id", "id", "dataset_doc_uuid")
    project = _first(raw_json, "project_key", "project", "project_name", "queue", "team")
    author = _first(raw_json, "reporter", "creator", "author", "assignee")
    timestamp = _first(raw_json, "created_at", "created", "updated_at", "updated", "timestamp")

    title = _first(raw_json, "summary", "title", "subject")
    body = _content_from_declared_fields(
        raw_json,
        ("description", "body", "content", "comments"),
    )
    content = f"{title}\n\n{body}".strip() if title else body

    excluded = {
        "issue_key",
        "key",
        "ticket_id",
        "id",
        "dataset_doc_uuid",
        "project_key",
        "project",
        "project_name",
        "queue",
        "team",
        "reporter",
        "creator",
        "author",
        "assignee",
        "created_at",
        "created",
        "updated_at",
        "updated",
        "timestamp",
        "summary",
        "title",
        "subject",
        "description",
        "body",
        "content",
        "comments",
    }
    return RawDocument(
        source="jira",
        source_id=str(source_id),
        author=str(author),
        timestamp=str(timestamp),
        content=content,
        container_id=str(project),
        metadata=_metadata_without(raw_json, excluded),
    )


def normalize_github(raw_json: dict[str, Any]) -> RawDocument:
    repo = _first(raw_json, "repo", "repository", "repository_name", "owner_repo")
    pr_number = _first(raw_json, "pr_number", "pull_request_number", "number")
    source_id = _first(
        raw_json,
        "id",
        "source_id",
        "dataset_doc_uuid",
        default=f"{repo}#{pr_number}" if repo and pr_number else "",
    )
    author = _first(raw_json, "author", "user", "creator")
    timestamp = _first(raw_json, "created_at", "updated_at", "merged_at", "closed_at")
    title = _first(raw_json, "title")
    body = _content_from_declared_fields(
        raw_json,
        ("description", "body", "content", "comments", "review_conversation"),
    )
    content = f"{title}\n\n{body}".strip() if title else body

    excluded = {
        "repo",
        "repository",
        "repository_name",
        "owner_repo",
        "pr_number",
        "pull_request_number",
        "number",
        "id",
        "source_id",
        "dataset_doc_uuid",
        "author",
        "user",
        "creator",
        "created_at",
        "updated_at",
        "merged_at",
        "closed_at",
        "title",
        "description",
        "body",
        "content",
        "comments",
        "review_conversation",
    }
    return RawDocument(
        source="github",
        source_id=str(source_id),
        author=str(author),
        timestamp=str(timestamp),
        content=content,
        container_id=str(repo),
        metadata=_metadata_without(raw_json, excluded),
    )


def normalize_gmail(raw_json: dict[str, Any]) -> RawDocument:
    thread_id = _first(raw_json, "thread_id", "id", "source_id", "dataset_doc_uuid")
    author = _first(raw_json, "sender", "from", "mailbox_owner", "author")
    timestamp = _first(raw_json, "first_email_at", "last_email_at", "timestamp", "date")
    subject = _first(raw_json, "subject", "title")
    body = _content_from_declared_fields(raw_json, ("messages", "body", "content", "text"))
    content = f"{subject}\n\n{body}".strip() if subject else body

    excluded = {
        "thread_id",
        "id",
        "source_id",
        "dataset_doc_uuid",
        "sender",
        "from",
        "mailbox_owner",
        "author",
        "first_email_at",
        "last_email_at",
        "timestamp",
        "date",
        "subject",
        "title",
        "messages",
        "body",
        "content",
        "text",
    }
    return RawDocument(
        source="gmail",
        source_id=str(thread_id),
        author=str(author),
        timestamp=str(timestamp),
        content=content,
        container_id=str(thread_id),
        metadata=_metadata_without(raw_json, excluded),
    )


ADAPTERS: dict[str, Callable[[dict[str, Any]], RawDocument]] = {
    "slack": normalize_slack,
    "jira": normalize_jira,
    "github": normalize_github,
    "gmail": normalize_gmail,
}


def load_records(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8-sig")
    if path.suffix.lower() == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]

    data = json.loads(text)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("records", "documents", "data", "items"):
            if isinstance(data.get(key), list):
                return data[key]
        return [data]

    raise ValueError(f"Unsupported JSON shape in {path}")


def parse_gmail_takeout(export_path: str | Path) -> list[dict[str, Any]]:
    """Parse a Google Takeout Gmail export into normalize_gmail-shaped records.

    Accepts either a single ``.mbox`` file or a Takeout directory containing
    ``.mbox`` files (e.g. ``Mail/All mail Including Spam and Trash.mbox``).
    Messages are threaded via the References/In-Reply-To chains, with a
    subject-based fallback for orphaned messages. Each returned dict has the
    keys ``normalize_gmail()`` reads: ``thread_id``, ``sender``, ``subject``,
    ``first_email_at``, ``last_email_at``, and ``messages``.
    """
    path = Path(export_path)
    if path.is_dir():
        mbox_files = sorted(item for item in path.rglob("*.mbox") if item.is_file())
        if not mbox_files:
            raise FileNotFoundError(f"No .mbox files found under {path}")
    else:
        if path.suffix.lower() != ".mbox":
            raise ValueError(f"Expected an .mbox file, got {path.suffix!r}")
        mbox_files = [path]

    messages: list[dict[str, Any]] = []
    for mbox_path in mbox_files:
        box = mailbox.mbox(str(mbox_path), create=False)
        try:
            for message in box:
                info = _gmail_message_info(message)
                if info is not None:
                    messages.append(info)
        finally:
            box.close()

    reference_map = {
        info["message_id"]: (info["references"][-1] if info["references"] else "")
        for info in messages
    }
    grouped: dict[str, list[dict[str, Any]]] = {}
    for info in messages:
        root = _thread_root(info["message_id"], reference_map)
        grouped.setdefault(root, []).append(info)

    # Orphaned messages (no references) are threaded by normalized subject so
    # flat exports without reference headers still group into conversations.
    merged: dict[str, list[dict[str, Any]]] = {}
    for root, items in grouped.items():
        key = root
        if len(items) == 1 and not items[0]["references"]:
            subject_key = _subject_key(items[0]["subject"])
            key = "subject:" + subject_key
        merged.setdefault(key, []).extend(items)

    records: list[dict[str, Any]] = []
    for items in merged.values():
        items.sort(key=lambda item: item["date"])
        first, last = items[0], items[-1]
        records.append(
            {
                "thread_id": items[0]["message_id"],
                "sender": first["sender"],
                "subject": first["subject"],
                "first_email_at": first["date"],
                "last_email_at": last["date"],
                "messages": [
                    {
                        "message_id": item["message_id"],
                        "sender": item["sender"],
                        "date": item["date"],
                        "subject": item["subject"],
                        "body": item["body"],
                    }
                    for item in items
                ],
            }
        )
    return records


def parse_slack_export(export_dir: str | Path) -> list[dict[str, Any]]:
    """Parse a Slack workspace export directory into normalize_slack-shaped records.

    Expects the standard export layout: ``channels.json`` and ``users.json``
    at the root plus one subdirectory per channel containing per-day JSON
    files of messages. User ids in ``text`` (``<@U123>``) are resolved to
    display names using ``users.json``. Each returned dict carries the keys
    ``normalize_slack()`` reads: ``message_id``, ``channel``, ``user_name``,
    ``timestamp``, and ``text``.
    """
    root = Path(export_dir)
    if not root.is_dir():
        raise FileNotFoundError(f"Slack export directory does not exist: {root}")

    users = _slack_users(root / "users.json")
    channels: dict[str, str] = {}
    channels_by_name: dict[str, str] = {}
    channels_file = root / "channels.json"
    if channels_file.exists():
        for channel in _load_json_array(channels_file):
            channel_id = str(channel.get("id") or "")
            channel_name = str(channel.get("name") or "")
            if channel_id:
                channels[channel_id] = channel_name
            if channel_name:
                channels_by_name[channel_name] = channel_id

    records: list[dict[str, Any]] = []
    channel_dirs = sorted(item for item in root.iterdir() if item.is_dir())
    for channel_dir in channel_dirs:
        channel_name = channel_dir.name
        channel_id = channels_by_name.get(channel_name, "")
        day_files = sorted(item for item in channel_dir.glob("*.json") if item.is_file())
        for day_file in day_files:
            for message in _load_json_array(day_file):
                if not isinstance(message, dict):
                    continue
                text = str(message.get("text") or "").strip()
                if not text:
                    continue
                ts = str(message.get("ts") or "")
                user = str(message.get("user") or message.get("bot_id") or message.get("username") or "")
                record: dict[str, Any] = {
                    "message_id": ts,
                    "channel": channel_name,
                    "channel_id": channel_id,
                    "user": user,
                    "user_name": _slack_user_name(user, users) or user,
                    "timestamp": ts,
                    "text": _resolve_slack_mentions(text, users),
                }
                if message.get("thread_ts"):
                    record["thread_ts"] = str(message["thread_ts"])
                if message.get("subtype"):
                    record["subtype"] = str(message["subtype"])
                if isinstance(message.get("replies"), list):
                    record["reply_count"] = len(message["replies"])
                records.append(record)
    return records


def _gmail_message_info(message: mailbox.Message) -> dict[str, Any] | None:
    raw_id = message.get("Message-ID")
    message_id = _message_header_id(raw_id) or (str(raw_id).strip() if raw_id else "")
    if not message_id:
        return None
    references = _message_header_ids(message.get("References"))
    references.extend(_message_header_ids(message.get("In-Reply-To")))
    return {
        "message_id": message_id,
        "references": references,
        "subject": str(message.get("Subject") or "").strip(),
        "sender": _email_sender(message),
        "date": _email_timestamp(message.get("Date")),
        "body": _email_body(message),
    }


def _message_header_id(value: str | None) -> str:
    if not value:
        return ""
    match = re.search(r"<([^<>]+)>", value)
    return match.group(1).strip() if match else ""


def _message_header_ids(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in re.findall(r"<([^<>]+)>", value) if item.strip()]


def _thread_root(message_id: str, reference_map: dict[str, str]) -> str:
    current = message_id
    visited: set[str] = set()
    while current in reference_map and current not in visited:
        visited.add(current)
        parent = reference_map[current]
        if not parent or parent == current:
            break
        current = parent
    return current


def _subject_key(subject: str) -> str:
    stripped = re.sub(r"^(re|fwd|fw|aw|sv|antw)\s*[::\-]\s*", "", subject, flags=re.IGNORECASE)
    return stripped.strip().casefold()


def _email_sender(message: mailbox.Message) -> str:
    raw = str(message.get("From") or "")
    if not raw:
        return ""
    from email.utils import getaddresses

    for name, address in getaddresses([raw]):
        if name.strip():
            return name.strip()
        if address.strip():
            return address.strip()
    # getaddresses can drop malformed (e.g. domainless) addresses; fall back
    # to the display name before '<' or the bare address itself.
    match = re.search(r"([^<]*?)\s*<\s*([^>]+)\s*>", raw)
    if match:
        name, address = match.groups()
        return name.strip() or address.strip()
    return raw.strip()


def _email_timestamp(value: str | None) -> str:
    if not value:
        return ""
    try:
        return parsedate_to_datetime(value).isoformat()
    except (TypeError, ValueError):
        return str(value).strip()


def _decode_payload(payload: bytes, charset: str | None) -> str:
    try:
        return payload.decode(charset or "utf-8", errors="replace")
    except (LookupError, ValueError):
        return payload.decode("utf-8", errors="replace")


def _email_body(message: mailbox.Message) -> str:
    if message.is_multipart():
        text_parts: list[str] = []
        html_parts: list[str] = []
        for part in message.walk():
            payload = part.get_payload(decode=True)
            if payload is None:
                continue
            content_type = part.get_content_type()
            if content_type == "text/plain":
                text_parts.append(_decode_payload(payload, part.get_content_charset()))
            elif content_type == "text/html":
                html_parts.append(re.sub(r"<[^>]+>", " ", _decode_payload(payload, part.get_content_charset())))
        if text_parts:
            return "\n\n".join(text_parts)
        if html_parts:
            return "\n\n".join(html_parts)
        return ""

    payload = message.get_payload(decode=True)
    if payload is None:
        return ""
    return _decode_payload(payload, message.get_content_charset())


def _load_json_array(path: Path) -> list[Any]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    return data if isinstance(data, list) else []


def _slack_users(path: Path) -> dict[str, str]:
    users: dict[str, str] = {}
    if not path.exists():
        return users
    for user in _load_json_array(path):
        if not isinstance(user, dict):
            continue
        user_id = str(user.get("id") or "")
        if not user_id:
            continue
        profile = user.get("profile") if isinstance(user.get("profile"), dict) else {}
        name = (
            str(profile.get("display_name") or "")
            or str(profile.get("real_name") or "")
            or str(user.get("name") or "")
        ).strip()
        if name:
            users[user_id] = name
    return users


def _slack_user_name(user_id: str, users: dict[str, str]) -> str:
    if user_id in users:
        return users[user_id]
    return user_id


def _resolve_slack_mentions(text: str, users: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        user_id = match.group(1)
        return f"@{users[user_id]}" if user_id in users else match.group(0)

    return re.sub(r"<@([A-Z0-9]+)>", replace, text)


def infer_source_type(path: Path, first_record: dict[str, Any]) -> str:
    lowered_parts = [part.lower() for part in path.parts]
    for source_type in ADAPTERS:
        if source_type in lowered_parts:
            return source_type

    keys = set(first_record)
    if {"repo", "pr_number"} & keys:
        return "github"
    if {"thread_id", "messages", "mailbox_owner"} & keys:
        return "gmail"
    if {"channel", "channel_id", "ts", "message"} & keys:
        return "slack"
    if {"issue_key", "project_key", "summary"} & keys:
        return "jira"

    raise ValueError("Could not infer source type; pass --source-type explicitly.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize EnterpriseRAG-Bench sample records.")
    parser.add_argument("sample_file", type=Path, help="Path to a JSON or JSONL sample file.")
    parser.add_argument(
        "--source-type",
        choices=sorted(ADAPTERS),
        help="Source adapter to use. Inferred from path or record keys when omitted.",
    )
    args = parser.parse_args()

    records = load_records(args.sample_file)
    if not records:
        print("No records found.")
        return

    source_type = args.source_type or infer_source_type(args.sample_file, records[0])
    adapter = ADAPTERS[source_type]
    normalized = [adapter(record) for record in records[:3]]

    print(json.dumps([asdict(record) for record in normalized], indent=2))


if __name__ == "__main__":
    main()
