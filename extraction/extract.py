"""Extract candidate graph items from normalized EnterpriseRAG-Bench documents."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
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
DEFAULT_MAX_CONTENT_CHARS = 300
GROQ_MODELS_ENDPOINT = "https://api.groq.com/openai/v1/models"
ALLOWED_ENTITY_TYPES = frozenset(
    {"Person", "Organization", "Project", "Document", "Issue", "Product", "Team"}
)
ENTITY_TYPE_NORMALIZATION = {
    "person": "Person",
    "org": "Organization",
    "organization": "Organization",
    "project": "Project",
    "document": "Document",
    "doc": "Document",
    "issue": "Issue",
    "ticket": "Issue",
    "product": "Product",
    "team": "Team",
}
GENERIC_ENTITY_STOPLIST = frozenset(
    {
        "api",
        "and",
        "application",
        "app",
        "all",
        "bug",
        "company",
        "data",
        "database",
        "document",
        "feature",
        "for",
        "from",
        "issue",
        "kms",
        "new",
        "none",
        "platform",
        "product",
        "project",
        "repository",
        "repo",
        "sdk",
        "se",
        "service",
        "sql",
        "system",
        "task",
        "team",
        "ticket",
        "the",
        "this",
        "that",
        "with",
        "user",
        "work",
    }
)


EXTRACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "candidate_entities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "type": {"type": "string", "enum": sorted(ALLOWED_ENTITY_TYPES)},
                    "aliases_hint": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["name", "type", "aliases_hint"],
                "additionalProperties": False,
            },
        },
        "candidate_relations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "source_entity": {"type": "string"},
                    "predicate": {"type": "string"},
                    "target_entity": {"type": "string"},
                },
                "required": ["source_entity", "predicate", "target_entity"],
                "additionalProperties": False,
            },
        },
        "candidate_facts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "subject_entity": {"type": "string"},
                    "predicate": {"type": "string"},
                    "value": {"type": "string"},
                    "stated_at": {"type": "string"},
                },
                "required": ["subject_entity", "predicate", "value", "stated_at"],
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
            get_groq_model(),
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


def get_groq_model() -> str:
    return os.environ.get("GROQ_MODEL", DEFAULT_GROQ_MODEL)


def list_groq_models(timeout_seconds: int = 30) -> list[str]:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is required to list Groq models.")

    response = httpx.get(
        GROQ_MODELS_ENDPOINT,
        headers={
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "cortex-hydradb-extractor/0.1",
        },
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    data = response.json().get("data", [])
    return sorted(model["id"] for model in data if "id" in model)


def build_messages(document: RawDocument, max_content_chars: int = DEFAULT_MAX_CONTENT_CHARS) -> list[dict[str, str]]:
    payload = {
        "source": document.source,
        "source_id": document.source_id,
        "author": document.author,
        "timestamp": document.timestamp,
        "container_id": document.container_id,
        "metadata": document.metadata,
        "content": document.content[:max_content_chars],
    }
    return [
        {
            "role": "system",
            "content": (
                "Extract enterprise knowledge graph candidates from normalized documents. "
                "Use concise canonical entity names. Only extract genuine named things: "
                "specific people, organizations or companies, named projects, named products, "
                "documents, issues or tickets, and teams. Do not extract generic technical "
                "terms, acronyms, or common nouns as standalone entities unless they are "
                "clearly a proper noun or named entity in context. For example, AWS KMS as a "
                "specific service reference is valid, but bare KMS or SE without a clear "
                "referent should not become a person or organization candidate. Entity type "
                "must be exactly one of Person, Organization, Project, Document, Issue, "
                "Product, or Team. Use stable snake_case predicates. Only extract claims "
                "supported by the document. Use the document timestamp when no better "
                "stated_at date is in the content. Return one JSON object with candidate_entities, "
                "candidate_relations, and candidate_facts arrays. Entity objects contain "
                "name, type, aliases_hint. Relation objects contain source_entity, "
                "predicate, target_entity. Fact objects contain subject_entity, predicate, "
                "value, stated_at."
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
    retries: int = 1,
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
    elif mode == "json_object":
        request_body["response_format"] = {"type": "json_object"}
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
        if exc.response.status_code == 429 and retries > 0:
            time.sleep(3)
            return chat_completion_json(
                provider=provider,
                messages=messages,
                timeout_seconds=timeout_seconds,
                strict_schema=strict_schema,
                mode=mode,
                retries=retries - 1,
            )
        if mode == "json_schema" and strict_schema and provider == "groq" and exc.response.status_code == 400:
            return chat_completion_json(
                provider=provider,
                messages=messages,
                timeout_seconds=timeout_seconds,
                strict_schema=False,
                mode="json_schema",
                retries=retries,
            )
        if mode == "json_schema" and provider == "groq" and exc.response.status_code == 400:
            return chat_completion_json(
                provider=provider,
                messages=messages,
                timeout_seconds=timeout_seconds,
                mode="tool_call",
                retries=retries,
            )
        if mode == "tool_call" and provider == "groq" and exc.response.status_code == 400:
            return chat_completion_json(
                provider=provider,
                messages=messages,
                timeout_seconds=timeout_seconds,
                mode="json_object",
                retries=retries,
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


def filter_candidate_entities(extraction: dict[str, Any]) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    for entity in extraction.get("candidate_entities") or []:
        if not isinstance(entity, dict):
            continue
        name = entity.get("name")
        entity_type = entity.get("type")
        if not isinstance(name, str) or not isinstance(entity_type, str):
            continue
        name = name.strip()
        normalized_type = ENTITY_TYPE_NORMALIZATION.get(entity_type.strip().casefold())
        if len(name) < 3 or normalized_type not in ALLOWED_ENTITY_TYPES:
            continue
        if name.casefold() in GENERIC_ENTITY_STOPLIST:
            continue
        entity["name"] = name
        entity["type"] = normalized_type
        filtered.append(entity)
    return filtered


def tag_source_doc_id(extraction: dict[str, Any], source_doc_id: str) -> dict[str, Any]:
    record_types = {
        "candidate_entities": "Entity",
        "candidate_relations": "Relation",
        "candidate_facts": "FactState",
    }
    extraction["candidate_entities"] = filter_candidate_entities(extraction)
    for collection, record_type in record_types.items():
        extraction.setdefault(collection, [])
        for item in extraction.get(collection, []):
            item["record_type"] = record_type
            item["source_doc_id"] = source_doc_id
    return extraction


def extract_from_document(
    document: RawDocument,
    provider: str = "auto",
    timeout_seconds: int = 60,
    max_content_chars: int = DEFAULT_MAX_CONTENT_CHARS,
) -> dict[str, Any]:
    load_dotenv(PROJECT_ROOT / ".env")
    chosen_provider = choose_provider(provider)
    extraction = chat_completion_json(
        provider=chosen_provider,
        messages=build_messages(document, max_content_chars=max_content_chars),
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
    parser.add_argument(
        "--list-groq-models",
        action="store_true",
        help="Print Groq model IDs available to the configured GROQ_API_KEY and exit.",
    )
    parser.add_argument(
        "--groq-model",
        default=None,
        help=f"Groq model ID. Defaults to GROQ_MODEL or {DEFAULT_GROQ_MODEL}.",
    )
    parser.add_argument("--limit", type=int, default=3, help="Number of documents to extract.")
    parser.add_argument(
        "--max-content-chars",
        type=int,
        default=DEFAULT_MAX_CONTENT_CHARS,
        help="Maximum document content characters sent to the LLM per sample.",
    )
    parser.add_argument("--timeout-seconds", type=int, default=60)
    args = parser.parse_args()

    load_dotenv(PROJECT_ROOT / ".env")
    if args.groq_model:
        os.environ["GROQ_MODEL"] = args.groq_model

    if args.list_groq_models:
        print(json.dumps(list_groq_models(args.timeout_seconds), indent=2))
        return

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
            max_content_chars=args.max_content_chars,
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
