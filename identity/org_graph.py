"""Sync the employee directory's manager/reports-to structure into HydraDB.

``sync_org_structure_to_graph(collection)`` reads every employee in a
collection and writes real graph edges into HydraDB:

- one lightweight ``Entity`` record (``entity_type="Person"``) per employee,
  linked by ``work_email`` as the identifier,
- a ``manages`` relation edge from each employee's manager to the employee,
  carried in a single ``RelationSet`` record.

The records mirror the shape produced by ``graph/ingest_to_hydradb.py`` so the
existing ingest pipeline, resolution pass, and ``answer_question``'s multi-hop
expansion all consume them unchanged. Call this after
``bulk_register_employees()`` completes to make org structure queryable.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

from hydra_db import HydraDB

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from graph.ingest_to_hydradb import (  # noqa: E402
    DATABASE_NAME,
    POLL_INTERVAL_SECONDS,
    POLL_TIMEOUT_SECONDS,
    build_ingest_payload,
    get_api_key,
    stable_id,
    to_plain_data,
)
from identity.employee_directory import list_employees  # noqa: E402

ORG_SOURCE_DOC_ID_PREFIX = "org-directory"
ENTITY_STATE = "candidate"  # matches graph ingestion; resolution treats it uniformly


def _employee_entity_id(collection: str, work_email: str) -> str:
    return f"entity-{stable_id('org', collection, work_email)}"


def build_org_graph_records(
    collection: str,
    employees: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any] | None, int]:
    """Build HydraDB source records for employees and their manages edges.

    Returns ``(entity_records, relation_record, skipped_missing_manager)``.
    A manager whose id is not in the directory gets a placeholder Person
    entity (named by id) so the edge still lands; those are counted in the
    skipped tally so callers can see the directory has dangling references.
    """
    by_id = {employee["employee_id"]: employee for employee in employees}
    entity_records: list[dict[str, Any]] = []
    graph_entities: dict[str, dict[str, Any]] = {}

    # First pass: one Entity record per employee (also registers the graph node).
    for employee in employees:
        entity_id = _employee_entity_id(collection, employee["work_email"])
        name = employee["name"]
        graph_entities[entity_id] = {
            "name": name,
            "type": "ENTITY",
            "namespace": "entities",
            "external_id": entity_id,
        }
        graph_entities[f"{entity_id}_candidate_state"] = {
            "name": ENTITY_STATE,
            "type": "ENTITY_STATE",
            "namespace": "states",
        }
        entity_records.append(
            {
                "id": entity_id,
                "title": f"Entity: {name}",
                "kind": "entity",
                "content": f"{name} is an employee of {collection}.",
                "metadata": {
                    "type": "Entity",
                    "record_type": "Entity",
                    "entity_type": "Person",
                    "canonical_name": name,
                    "email": employee["work_email"],
                    "source_doc_id": f"{ORG_SOURCE_DOC_ID_PREFIX}:{collection}",
                    "confidence": 0.9,
                    "state": ENTITY_STATE,
                    "access_level": "internal",
                },
                "additional_metadata": {
                    "aliases": [name, employee["work_email"]],
                    "employee_id": employee["employee_id"],
                    "source_doc_id": f"{ORG_SOURCE_DOC_ID_PREFIX}:{collection}",
                },
                "graph_entities": {
                    entity_id: graph_entities[entity_id],
                    f"{entity_id}_candidate_state": graph_entities[f"{entity_id}_candidate_state"],
                },
                "graph_relations": [
                    {
                        "source": entity_id,
                        "target": f"{entity_id}_candidate_state",
                        "predicate": "HAS_STATE",
                        "context": f"{name} is a {ENTITY_STATE} employee entity.",
                    }
                ],
            }
        )

    # Second pass: manages edges.
    relations: list[dict[str, Any]] = []
    skipped_missing_manager = 0
    for employee in employees:
        manager_ref = employee.get("manager_employee_id")
        if not manager_ref:
            continue
        target_id = _employee_entity_id(collection, employee["work_email"])
        manager = by_id.get(manager_ref)
        if manager:
            source_id = _employee_entity_id(collection, manager["work_email"])
            context = f"{manager['name']} manages {employee['name']}"
        else:
            source_id = f"entity-{stable_id('org', collection, 'person', manager_ref)}"
            graph_entities.setdefault(
                source_id,
                {
                    "name": manager_ref,
                    "type": "ENTITY",
                    "namespace": "entities",
                    "external_id": source_id,
                },
            )
            context = f"{manager_ref} manages {employee['name']} (manager not in directory)"
            skipped_missing_manager += 1
        relations.append(
            {
                "source": source_id,
                "target": target_id,
                "predicate": "manages",
                "context": context,
            }
        )

    relation_record = None
    if relations:
        relation_record = {
            "id": f"relations-{stable_id('org', collection)}",
            "title": f"Org structure for {collection}",
            "kind": "relation",
            "content": f"Manager/reports-to edges for {collection}.",
            "metadata": {
                "type": "RelationSet",
                "record_type": "Relation",
                "source_doc_id": f"{ORG_SOURCE_DOC_ID_PREFIX}:{collection}",
                "doc_source_type": ORG_SOURCE_DOC_ID_PREFIX,
                "confidence": 0.9,
                "state": ENTITY_STATE,
                "access_level": "internal",
            },
            "additional_metadata": {
                "source_doc_id": f"{ORG_SOURCE_DOC_ID_PREFIX}:{collection}",
            },
            "graph_entities": graph_entities,
            "graph_relations": relations,
        }

    return entity_records, relation_record, skipped_missing_manager


def _wait_for_ingestion(client: HydraDB, database: str, collection: str, ids: list[str]) -> None:
    """Poll ingestion status quietly until every record settles (or timeout)."""
    deadline = time.monotonic() + POLL_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        response = client.context.status(database=database, collection=collection, ids=ids)
        statuses = to_plain_data(response.data.statuses)
        states = {status["id"]: status["indexing_status"] for status in statuses}
        if all(state in {"completed", "errored"} for state in states.values()):
            errored = [record_id for record_id, state in states.items() if state == "errored"]
            if errored:
                raise RuntimeError(f"Org structure ingestion errored for records: {errored}")
            return
        time.sleep(POLL_INTERVAL_SECONDS)
    raise TimeoutError(f"Timed out waiting for org structure ingestion of {ids}.")


def sync_org_structure_to_graph(
    collection: str,
    database: str = DATABASE_NAME,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Write the manager/reports-to org structure for ``collection`` into HydraDB.

    Idempotent: records are upserted by stable ids derived from collection and
    work email, so re-running after directory updates refreshes edges without
    duplicating entities. ``dry_run=True`` returns the prepared summary without
    touching HydraDB.
    """
    if not str(collection).strip():
        raise ValueError("collection must not be empty.")

    employees = list_employees(str(collection).strip())
    if not employees:
        return {
            "entities_created": 0,
            "edges_created": 0,
            "skipped_missing_manager": 0,
            "dry_run": dry_run,
        }

    entity_records, relation_record, skipped = build_org_graph_records(
        str(collection).strip(), employees
    )
    records = entity_records + ([relation_record] if relation_record else [])
    edges_created = len(relation_record["graph_relations"]) if relation_record else 0

    if dry_run:
        return {
            "entities_created": len(entity_records),
            "edges_created": edges_created,
            "skipped_missing_manager": skipped,
            "dry_run": True,
        }

    client = HydraDB(token=get_api_key())
    app_knowledge, graph_payload = build_ingest_payload(records, database)
    response = client.context.ingest(
        type="knowledge",
        database=database,
        collection=str(collection).strip(),
        upsert=True,
        app_knowledge=json.dumps(app_knowledge),
        graph_payload=json.dumps(graph_payload),
    )
    to_plain_data(response)  # surface any API error
    _wait_for_ingestion(client, database, str(collection).strip(), [record["id"] for record in records])

    return {
        "entities_created": len(entity_records),
        "edges_created": edges_created,
        "skipped_missing_manager": skipped,
        "dry_run": False,
    }
