"""Extract candidate graph items from normalized EnterpriseRAG-Bench documents."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

import httpx


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ingestion.normalize import ADAPTERS, RawDocument, infer_source_type, load_records


DEFAULT_GROQ_MODEL = "openai/gpt-oss-20b"
DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"
MAX_CONTENT_CHARS = 12_000


EXTRACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "candidate_entities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "record_type": {"type": "string", "enum": ["Entity"]},
                    "source_doc_id": {"type": "string"},
                    "name": {"type": "string"},
                    "entity_type": {"type": "string"},
                    "aliases_hint": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["record_type", "source_doc_id", "name", "entity_type", "aliases_hint"],
                "additionalProperties": False,
            },
        },
        "candidate_relations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "record_type": {"type": "string", "enum": ["Relation"]},
                    "source_doc_id": {"type": "string"},
                    "source_entity": {"type": "string"},
                    "predicate": {"type": "string"},
                    "target_entity": {"type": "string"},
                },
                "required": [
                    "record_type",
                    "source_doc_id",
                    "source_entity",
                    "predicate",
                    "target_entity",
                ],
                "additionalProperties": False,
            },
        },
        "candidate_facts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "record_type": {"type": "string", "enum": ["FactState"]},
                    "source_doc_id": {"type": "string"},
                    "subject_entity": {"type": "string"},
                    "predicate": {"type": "string"},
                    "value": {"type": "string"},
                    "stated_at": {"type": "string"},
                },
                "required": [
                    "record_type",
                    "source_doc_id",
                    "subject_entity",
                    "predicate",
                    "value",
                    "stated_at",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": ["candidate_entities", "candidate_relations", "candidate_facts"],
    "additionalProperties": False,
}


def load_dotenv(path: str | Path = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return

    with env_path.open(encoding="utf-8") as env_file:
        for line in env_file:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def choose_provider(provider: str) -> str:
    if provider != "auto":
        return provider
    if os.environ.get("GROQ_API_KEY"):
        return "groq"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    raise RuntimeError("Set GROQ_API_KEY or OPENAI_API_KEY in the environment or .env.")


def provider_config(provider: str) -> tuple[str, str, str]:
    if provider == "groq":
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY is required for provider=groq.")
        return (
            "https://api.groq.com/openai/v1/chat/completions",
            api_key,
            os.environ.get("GROQ_MODEL", DEFAULT_GROQ_MODEL),
        )

    if provider == "openai":
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required for provider=openai.")
        return (
            "https://api.openai.com/v1/chat/completions",
            api_key,
            os.environ.get("OPENAI_MODEL", DEFAULT_OPENAI_MODEL),
        )

    raise ValueError(f"Unsupported provider: {provider}")


def build_messages(document: RawDocument) -> list[dict[str, str]]:
    payload = {
        "source": document.source,
        "source_id": document.source_id,
        "author": document.author,
        "timestamp": document.timestamp,
        "container_id": document.container_id,
        "metadata": document.metadata,
        "content": document.content[:MAX_CONTENT_CHARS],
    }
    return [
        {
            "role": "system",
            "content": (
                "Extract enterprise knowledge graph candidates from normalized documents. "
                "Use concise canonical entity names, uppercase entity types such as PERSON, "
                "ORG, PROJECT, ACCOUNT, TICKET, REPOSITORY, DOCUMENT, FEATURE, or SYSTEM, "
                "and stable snake_case predicates. Only extract claims supported by the "
                "document. Use the document timestamp when no better stated_at date is in "
                "the content. Every item must use the provided source_doc_id exactly."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(payload, ensure_ascii=False, sort_keys=True),
        },
    ]


def chat_completion_json(
    provider: str,
    messages: list[dict[str, str]],
    timeout_seconds: int,
    strict_schema: bool = True,
    mode: str = "json_schema",
) -> dict[str, Any]:
    endpoint, api_key, model = provider_config(provider)
    request_body = {
        "model": model,
        "messages": messages,
        "temperature": 0,
    }

    if mode == "json_schema":
        request_body["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": "enterprise_rag_extraction",
                "strict": strict_schema,
                "schema": EXTRACTION_SCHEMA,
            },
        }
    elif mode == "tool_call":
        request_body["tools"] = [
            {
                "type": "function",
                "function": {
                    "name": "submit_extraction",
                    "description": "Submit extracted enterprise knowledge graph candidates.",
                    "parameters": EXTRACTION_SCHEMA,
                },
            }
        ]
        request_body["tool_choice"] = {
            "type": "function",
            "function": {"name": "submit_extraction"},
        }
    else:
        raise ValueError(f"Unsupported structured output mode: {mode}")
    try:
        response = httpx.post(
            endpoint,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "cortex-hydradb-extractor/0.1",
            },
            json=request_body,
            timeout=timeout_seconds,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        if mode == "json_schema" and strict_schema and provider == "groq" and exc.response.status_code == 400:
            return chat_completion_json(
                provider=provider,
                messages=messages,
                timeout_seconds=timeout_seconds,
                strict_schema=False,
                mode="json_schema",
            )
        if mode == "json_schema" and provider == "groq" and exc.response.status_code == 400:
            return chat_completion_json(
                provider=provider,
                messages=messages,
                timeout_seconds=timeout_seconds,
                mode="tool_call",
            )
        raise RuntimeError(
            f"{provider} API returned HTTP {exc.response.status_code}: {exc.response.text}"
        ) from exc

    response_body = response.json()
    message = response_body["choices"][0]["message"]
    tool_calls = message.get("tool_calls") or []
    if tool_calls:
        return json.loads(tool_calls[0]["function"]["arguments"])

    return json.loads(message["content"])


def tag_source_doc_id(extraction: dict[str, Any], source_doc_id: str) -> dict[str, Any]:
    record_types = {
        "candidate_entities": "Entity",
        "candidate_relations": "Relation",
        "candidate_facts": "FactState",
    }
    for collection, record_type in record_types.items():
        for item in extraction.get(collection, []):
            item["record_type"] = record_type
            item["source_doc_id"] = source_doc_id
    return extraction


def extract_from_document(
    document: RawDocument,
    provider: str = "auto",
    timeout_seconds: int = 60,
) -> dict[str, Any]:
    load_dotenv(PROJECT_ROOT / ".env")
    chosen_provider = choose_provider(provider)
    extraction = chat_completion_json(
        provider=chosen_provider,
        messages=build_messages(document),
        timeout_seconds=timeout_seconds,
    )
    return tag_source_doc_id(extraction, document.source_id)


def raw_document_from_json(raw_json: dict[str, Any]) -> RawDocument:
    return RawDocument(
        source=str(raw_json.get("source", "")),
        source_id=str(raw_json.get("source_id", "")),
        author=str(raw_json.get("author", "")),
        timestamp=str(raw_json.get("timestamp", "")),
        content=str(raw_json.get("content", "")),
        container_id=str(raw_json.get("container_id", "")),
        metadata=dict(raw_json.get("metadata") or {}),
    )


def normalize_sample_docs(
    sample_file: Path,
    source_type: str | None,
    already_normalized: bool,
    limit: int,
) -> list[RawDocument]:
    records = load_records(sample_file)
    if already_normalized:
        return [raw_document_from_json(record) for record in records[:limit]]

    if not records:
        return []
    inferred_source_type = source_type or infer_source_type(sample_file, records[0])
    adapter = ADAPTERS[inferred_source_type]
    return [adapter(record) for record in records[:limit]]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract candidate entities, relations, and facts from normalized docs."
    )
    parser.add_argument("sample_file", type=Path, help="Path to a raw or normalized JSON/JSONL sample.")
    parser.add_argument(
        "--source-type",
        choices=sorted(ADAPTERS),
        help="Source adapter for raw EnterpriseRAG-Bench records.",
    )
    parser.add_argument(
        "--normalized",
        action="store_true",
        help="Treat sample_file records as already-normalized RawDocument JSON.",
    )
    parser.add_argument("--provider", choices=("auto", "groq", "openai"), default="auto")
    parser.add_argument("--limit", type=int, default=3, help="Number of documents to extract.")
    parser.add_argument("--timeout-seconds", type=int, default=60)
    args = parser.parse_args()

    load_dotenv(PROJECT_ROOT / ".env")
    docs = normalize_sample_docs(
        sample_file=args.sample_file,
        source_type=args.source_type,
        already_normalized=args.normalized,
        limit=args.limit,
    )
    if not docs:
        print("No sample documents found.")
        return

    results = []
    for document in docs:
        extraction = extract_from_document(
            document,
            provider=args.provider,
            timeout_seconds=args.timeout_seconds,
        )
        results.append(
            {
                "document": asdict(document),
                "extraction": extraction,
            }
        )

    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
