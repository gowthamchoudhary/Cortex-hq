"""Normalize EnterpriseRAG-Bench records into a shared RawDocument shape."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
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
