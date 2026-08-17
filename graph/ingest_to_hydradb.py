"""Ingest extracted graph candidates into HydraDB."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hydra_db import HydraDB


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from schema.setup_database import DATABASE_METADATA_SCHEMA


DATABASE_NAME = "hackhydra-track1"
BATCH_SIZE = 20
POLL_INTERVAL_SECONDS = 5
POLL_TIMEOUT_SECONDS = 300
VALID_TO_SENTINEL = 9_999_999_999
ACCESS_LEVELS = ("public", "internal", "restricted")

ENTITY_TYPE_MAP = {
    "PERSON": "Person",
    "PEOPLE": "Person",
    "ORG": "Organization",
    "ORGANIZATION": "Organization",
    "ACCOUNT": "Account",
    "PROJECT": "Project",
    "DOCUMENT": "Document",
    "DOC": "Document",
    "ISSUE": "Issue",
    "TICKET": "Issue",
    "REPOSITORY": "Repository",
    "REPO": "Repository",
    "FEATURE": "Feature",
    "SYSTEM": "System",
    "FACT_STATE": "FactState",
}


def load_dotenv(path: Path = PROJECT_ROOT / ".env") -> None:
    if not path.exists():
        return
    with path.open(encoding="utf-8") as env_file:
        for line in env_file:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def get_api_key() -> str:
    load_dotenv()
    api_key = os.environ.get("HYDRADB_API_KEY")
    if not api_key:
        raise RuntimeError("HYDRADB_API_KEY environment variable is required.")
    return api_key


def to_plain_data(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return to_plain_data(value.model_dump())
    if hasattr(value, "dict"):
        return to_plain_data(value.dict())
    if isinstance(value, dict):
        return {key: to_plain_data(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_plain_data(item) for item in value]
    if hasattr(value, "__dict__"):
        return to_plain_data(vars(value))
    return value


def stable_id(*parts: Any) -> str:
    payload = "|".join(str(part) for part in parts if part not in (None, ""))
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:24]


def slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return normalized[:80] or "item"


def confidence(item: dict[str, Any], default: float = 0.5) -> float:
    value = item.get("confidence", default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def map_entity_type(raw_type: str | None) -> str:
    if not raw_type:
        return "Entity"
    return ENTITY_TYPE_MAP.get(str(raw_type).upper(), str(raw_type).title())


def unix_timestamp(value: Any, default: int) -> int:
    if value in (None, ""):
        return default
    if isinstance(value, (int, float)):
        return int(value)

    text = str(value).strip()
    if text.isdigit():
        return int(text)

    candidates = [
        text,
        text.replace("Z", "+00:00"),
        text[:10],
    ]
    for candidate in candidates:
        try:
            parsed = datetime.fromisoformat(candidate)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return int(parsed.timestamp())
        except ValueError:
            continue

    match = re.search(r"(\d{4})[-/](\d{2})[-/](\d{2})", text)
    if match:
        parsed = datetime(
            int(match.group(1)),
            int(match.group(2)),
            int(match.group(3)),
            tzinfo=timezone.utc,
        )
        return int(parsed.timestamp())

    return default


def load_extraction_records(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(data, dict):
        if "results" in data and isinstance(data["results"], list):
            return data["results"]
        return [data]
    if isinstance(data, list):
        return data
    raise ValueError(f"Unsupported extraction output shape in {path}")


def extract_document_and_payload(record: dict[str, Any]) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    document = record.get("document") or {}
    extraction = record.get("extraction") or record
    return document, {
        "candidate_entities": list(extraction.get("candidate_entities") or []),
        "candidate_relations": list(extraction.get("candidate_relations") or []),
        "candidate_facts": list(extraction.get("candidate_facts") or []),
    }


def build_graph_documents(
    records: list[dict[str, Any]],
    limit: int | None,
    default_access_level: str = "public",
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    now = int(time.time())
    graph_sources: list[dict[str, Any]] = []
    summary = {
        "entities_created": 0,
        "facts_created": 0,
        "relations_created": 0,
        "failures": 0,
    }

    for record in records:
        document, extraction = extract_document_and_payload(record)
        doc_source_id = str(document.get("source_id") or "")
        doc_source_type = str(document.get("source") or "")
        doc_timestamp = document.get("timestamp") or ""

        if not doc_source_id:
            for collection in extraction.values():
                if collection:
                    doc_source_id = str(collection[0].get("source_doc_id") or "")
                    break
        if not doc_source_id:
            summary["failures"] += 1
            continue

        entity_name_to_id: dict[str, str] = {}
        source_entities: dict[str, dict[str, Any]] = {}

        for entity in extraction["candidate_entities"]:
            name = str(entity.get("name") or "").strip()
            if not name:
                continue
            entity_type = map_entity_type(entity.get("type") or entity.get("entity_type"))
            entity_id = f"entity-{stable_id(doc_source_id, name)}"
            entity_name_to_id[name.lower()] = entity_id
            source_entities[entity_id] = {
                "name": name,
                "type": entity_type.upper(),
                "namespace": "entities",
                "external_id": entity_id,
            }
            graph_sources.append(
                {
                    "id": entity_id,
                    "title": f"Entity: {name}",
                    "kind": "entity",
                    "content": f"{name} is a candidate {entity_type} entity.",
                    "metadata": {
                        "type": "Entity",
                        "record_type": "Entity",
                        "entity_type": entity_type,
                        "canonical_name": name,
                        "source_doc_id": doc_source_id,
                        "confidence": confidence(entity),
                        "state": "candidate",
                        "access_level": default_access_level,
                    },
                    "additional_metadata": {
                        "aliases": list(entity.get("aliases_hint") or [name]),
                        "source_doc_id": doc_source_id,
                    },
                    "graph_entities": {
                        entity_id: source_entities[entity_id],
                        f"{entity_id}_candidate_state": {
                            "name": "candidate",
                            "type": "ENTITY_STATE",
                            "namespace": "states",
                        },
                    },
                    "graph_relations": [
                        {
                            "source": entity_id,
                            "target": f"{entity_id}_candidate_state",
                            "predicate": "HAS_STATE",
                            "context": f"{name} is a candidate entity extracted from {doc_source_id}.",
                        }
                    ],
                }
            )
            summary["entities_created"] += 1

        for fact in extraction["candidate_facts"]:
            subject_name = str(fact.get("subject_entity") or "").strip()
            predicate = str(fact.get("predicate") or "").strip()
            value = str(fact.get("value") or "").strip()
            if not subject_name or not predicate or not value:
                continue

            subject_id = entity_name_to_id.get(subject_name.lower())
            if not subject_id:
                subject_id = f"entity-{stable_id(doc_source_id, subject_name)}"
                entity_name_to_id[subject_name.lower()] = subject_id

            fact_id = f"fact-{stable_id(doc_source_id, subject_name, predicate, value)}"
            fact_node = f"{fact_id}_node"
            valid_from = unix_timestamp(fact.get("stated_at") or doc_timestamp, now)
            graph_sources.append(
                {
                    "id": fact_id,
                    "title": f"FactState: {subject_name} {predicate}",
                    "kind": "fact_state",
                    "content": f"{subject_name} {predicate}: {value}",
                    "metadata": {
                        "type": "FactState",
                        "record_type": "FactState",
                        "subject_id": subject_id,
                        "predicate": predicate,
                        "source_doc_id": doc_source_id,
                        "doc_source_type": doc_source_type,
                        "valid_from": valid_from,
                        "valid_to": VALID_TO_SENTINEL,
                        "txn_from": now,
                        "txn_to": VALID_TO_SENTINEL,
                        "authority_weight": 0.5,
                        "corroboration_count": 1,
                        "confidence": confidence(fact),
                        "state": "candidate",
                        "access_level": default_access_level,
                    },
                    "additional_metadata": {"value": value},
                    "graph_entities": {
                        subject_id: {
                            "name": subject_name,
                            "type": "ENTITY",
                            "namespace": "entities",
                            "external_id": subject_id,
                        },
                        fact_node: {
                            "name": f"{subject_name} {predicate} {value}",
                            "type": "FACT_STATE",
                            "namespace": "facts",
                            "external_id": fact_id,
                        },
                    },
                    "graph_relations": [
                        {
                            "source": subject_id,
                            "target": fact_node,
                            "predicate": predicate,
                            "context": f"{subject_name} {predicate}: {value}",
                            "temporal": f"{valid_from}-{VALID_TO_SENTINEL}",
                        }
                    ],
                }
            )
            summary["facts_created"] += 1

        relation_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        relation_entities: dict[str, dict[str, Any]] = {}
        for relation in extraction["candidate_relations"]:
            source_name = str(relation.get("source_entity") or "").strip()
            target_name = str(relation.get("target_entity") or "").strip()
            predicate = str(relation.get("predicate") or "").strip()
            if not source_name or not target_name or not predicate:
                continue

            source_id = entity_name_to_id.get(source_name.lower()) or f"entity-{stable_id(doc_source_id, source_name)}"
            target_id = entity_name_to_id.get(target_name.lower()) or f"entity-{stable_id(doc_source_id, target_name)}"
            relation_entities[source_id] = {
                "name": source_name,
                "type": "ENTITY",
                "namespace": "entities",
                "external_id": source_id,
            }
            relation_entities[target_id] = {
                "name": target_name,
                "type": "ENTITY",
                "namespace": "entities",
                "external_id": target_id,
            }
            relation_groups[doc_source_id].append(
                {
                    "source": source_id,
                    "target": target_id,
                    "predicate": predicate,
                    "context": f"{source_name} {predicate} {target_name}",
                }
            )
            summary["relations_created"] += 1

        if relation_groups[doc_source_id]:
            relation_source_id = f"relations-{stable_id(doc_source_id)}"
            graph_sources.append(
                {
                    "id": relation_source_id,
                    "title": f"Relations from {doc_source_id}",
                    "kind": "relation",
                    "content": f"Candidate relations extracted from {doc_source_id}.",
                    "metadata": {
                        "type": "RelationSet",
                        "record_type": "Relation",
                        "source_doc_id": doc_source_id,
                        "doc_source_type": doc_source_type,
                        "confidence": 0.5,
                        "state": "candidate",
                        "access_level": default_access_level,
                    },
                    "additional_metadata": {"source_doc_id": doc_source_id},
                    "graph_entities": relation_entities,
                    "graph_relations": relation_groups[doc_source_id],
                }
            )

        if limit is not None and len(graph_sources) >= limit:
            return graph_sources[:limit], summary

    return graph_sources, summary


def build_ingest_payload(batch: list[dict[str, Any]], database: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    app_knowledge = []
    graph_payload = {}
    for item in batch:
        source_id = item["id"]
        app_knowledge.append(
            {
                "id": source_id,
                "database": database,
                "title": item["title"],
                "type": item["kind"],
                "content": {"text": item["content"]},
                "metadata": item["metadata"],
                "additional_metadata": item["additional_metadata"],
            }
        )
        graph_payload[source_id] = {
            "entities": item["graph_entities"],
            "relations": item["graph_relations"],
        }
    return app_knowledge, graph_payload


def update_metadata_schema(client: HydraDB, database: str) -> None:
    try:
        response = client.databases.update_metadata_schema(
            database,
            add_fields=DATABASE_METADATA_SCHEMA,
        )
        print(f"Metadata schema update response: {to_plain_data(response)}")
    except Exception as exc:
        print(f"Metadata schema update skipped/failed: {exc}")


def ingest_batch(client: HydraDB, database: str, collection: str, batch: list[dict[str, Any]]) -> list[str]:
    app_knowledge, graph_payload = build_ingest_payload(batch, database)
    response = client.context.ingest(
        type="knowledge",
        database=database,
        collection=collection,
        upsert=True,
        app_knowledge=json.dumps(app_knowledge),
        graph_payload=json.dumps(graph_payload),
    )
    print(json.dumps(to_plain_data(response), indent=2, default=str))
    return [item["id"] for item in batch]


def wait_for_ingestion(client: HydraDB, database: str, collection: str, ids: list[str]) -> list[dict[str, Any]]:
    deadline = time.monotonic() + POLL_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        response = client.context.status(database=database, collection=collection, ids=ids)
        statuses = to_plain_data(response.data.statuses)
        states = {status["id"]: status["indexing_status"] for status in statuses}
        print(f"Ingestion status: {states}")

        if all(state in {"completed", "errored"} for state in states.values()):
            return statuses
        time.sleep(POLL_INTERVAL_SECONDS)
    raise TimeoutError(f"Timed out waiting for ingestion of {ids}.")


def batched(items: list[dict[str, Any]], batch_size: int) -> list[list[dict[str, Any]]]:
    return [items[index : index + batch_size] for index in range(0, len(items), batch_size)]


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest extracted graph candidates into HydraDB.")
    parser.add_argument("extraction_output", type=Path)
    parser.add_argument("--database", default=DATABASE_NAME)
    parser.add_argument("--collection", default="default")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    parser.add_argument("--default-access-level", choices=ACCESS_LEVELS, default="public")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-schema-update", action="store_true")
    args = parser.parse_args()

    try:
        records = load_extraction_records(args.extraction_output)
        graph_sources, summary = build_graph_documents(
            records,
            args.limit,
            default_access_level=args.default_access_level,
        )
        print(
            "Prepared "
            f"{summary['entities_created']} entities, "
            f"{summary['facts_created']} facts, "
            f"{summary['relations_created']} relations, "
            f"{summary['failures']} failures."
        )
        print(f"HydraDB source records to ingest: {len(graph_sources)}")

        if args.dry_run:
            preview = graph_sources[: min(3, len(graph_sources))]
            print(json.dumps(preview, indent=2, default=str))
            return 0

        client = HydraDB(token=get_api_key())
        if not args.skip_schema_update:
            update_metadata_schema(client, args.database)

        failed_statuses: list[dict[str, Any]] = []
        for index, batch in enumerate(batched(graph_sources, args.batch_size), start=1):
            print(f"Ingesting batch {index} with {len(batch)} records into collection {args.collection!r}...")
            ids = ingest_batch(client, args.database, args.collection, batch)
            statuses = wait_for_ingestion(client, args.database, args.collection, ids)
            failed_statuses.extend(
                status for status in statuses if status.get("indexing_status") == "errored"
            )
            time.sleep(1)

        print("Ingestion summary:")
        print(f"- entities created: {summary['entities_created']}")
        print(f"- facts created: {summary['facts_created']}")
        print(f"- relations created: {summary['relations_created']}")
        print(f"- extraction/load failures: {summary['failures']}")
        print(f"- HydraDB failures: {len(failed_statuses)}")
        if failed_statuses:
            print(json.dumps(failed_statuses, indent=2, default=str))
            return 1
        return 0
    except Exception as exc:
        print(f"HydraDB graph ingestion failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
