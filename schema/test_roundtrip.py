"""Round-trip a small Entity/FactState graph through HydraDB."""

import json
import os
import sys
import time
from typing import Any

from hydra_db import HydraDB


DATABASE_NAME = "hackhydra-track1"
ENTITY_ID = "entity-sam-ratnaparkhi"
FACT_ID = "fact-sam-ratnaparkhi-status-current"
POLL_INTERVAL_SECONDS = 5
POLL_TIMEOUT_SECONDS = 300


def load_dotenv(path: str = ".env") -> None:
    if not os.path.exists(path):
        return

    with open(path, encoding="utf-8") as env_file:
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


def ingest_test_records(client: HydraDB) -> list[str]:
    valid_from = int(time.time())
    valid_to = 9_999_999_999

    app_knowledge = [
        {
            "id": ENTITY_ID,
            "database": DATABASE_NAME,
            "title": "Entity: Sam Ratnaparkhi",
            "type": "entity",
            "content": {"text": "Sam Ratnaparkhi is a resolved Person entity."},
            "metadata": {
                "type": "Entity",
                "entity_type": "Person",
                "canonical_name": "Sam Ratnaparkhi",
                "subject_id": ENTITY_ID,
                "state": "resolved",
                "confidence": 1.0,
            },
            "additional_metadata": {"aliases": ["Sam", "@soham"]},
        },
        {
            "id": FACT_ID,
            "database": DATABASE_NAME,
            "title": "FactState: Sam Ratnaparkhi status",
            "type": "fact_state",
            "content": {
                "text": "Sam Ratnaparkhi has current status value on_track."
            },
            "metadata": {
                "type": "FactState",
                "subject_id": ENTITY_ID,
                "predicate": "status",
                "state": "current",
                "valid_from": valid_from,
                "valid_to": valid_to,
                "confidence": 1.0,
            },
            "additional_metadata": {"value": "on_track"},
        },
    ]

    graph_payload = {
        ENTITY_ID: {
            "entities": {
                "sam": {
                    "name": "Sam Ratnaparkhi",
                    "type": "PERSON",
                    "namespace": "people",
                    "external_id": ENTITY_ID,
                },
                "resolved_identity": {
                    "name": "Resolved identity",
                    "type": "ENTITY_STATE",
                    "namespace": "entity_states",
                }
            },
            "relations": [
                {
                    "source": "sam",
                    "target": "resolved_identity",
                    "predicate": "HAS_STATE",
                    "context": "Sam Ratnaparkhi is a resolved Person entity.",
                }
            ],
        },
        FACT_ID: {
            "entities": {
                "sam": {
                    "name": "Sam Ratnaparkhi",
                    "type": "PERSON",
                    "namespace": "people",
                    "external_id": ENTITY_ID,
                },
                "status_fact": {
                    "name": "Sam Ratnaparkhi status on_track",
                    "type": "FACT_STATE",
                    "namespace": "facts",
                    "external_id": FACT_ID,
                },
            },
            "relations": [
                {
                    "source": "sam",
                    "target": "status_fact",
                    "predicate": "status",
                    "context": "Sam Ratnaparkhi currently has status on_track.",
                    "temporal": f"{valid_from}-{valid_to}",
                }
            ],
        },
    }

    response = client.context.ingest(
        type="knowledge",
        database=DATABASE_NAME,
        upsert=True,
        app_knowledge=json.dumps(app_knowledge),
        graph_payload=json.dumps(graph_payload),
    )

    data = to_plain_data(response)
    print("Ingest response:")
    print(json.dumps(data, indent=2, sort_keys=True, default=str))
    return [ENTITY_ID, FACT_ID]


def wait_for_ingestion(client: HydraDB, ids: list[str]) -> None:
    deadline = time.monotonic() + POLL_TIMEOUT_SECONDS

    while time.monotonic() < deadline:
        response = client.context.status(database=DATABASE_NAME, ids=ids)
        statuses = to_plain_data(response.data.statuses)
        states = {status["id"]: status["indexing_status"] for status in statuses}
        print(f"Ingestion status: {states}")

        errors = [status for status in statuses if status["indexing_status"] == "errored"]
        if errors:
            raise RuntimeError(f"HydraDB ingestion failed: {errors}")

        if all(state == "completed" for state in states.values()):
            print("Ingestion completed.")
            return

        time.sleep(POLL_INTERVAL_SECONDS)

    raise TimeoutError(f"Timed out waiting for ingestion of {ids}.")


def query_fact_state(client: HydraDB) -> Any:
    result = client.query(
        database=DATABASE_NAME,
        query="Sam Ratnaparkhi current status on_track",
        type="knowledge",
        query_by="hybrid",
        mode="fast",
        max_results=5,
        metadata_filters={"subject_id": ENTITY_ID, "state": "current"},
    )

    plain_result = to_plain_data(result)
    print("Query result:")
    print(json.dumps(plain_result, indent=2, sort_keys=True, default=str))
    return plain_result


def confirm_round_trip(result: Any) -> None:
    serialized = json.dumps(result, default=str)
    required_values = [ENTITY_ID, "current", "on_track", "status"]
    missing_values = [value for value in required_values if value not in serialized]

    if missing_values:
        raise RuntimeError(
            "Round trip query did not return expected values: "
            + ", ".join(missing_values)
        )

    print("Round trip confirmed end to end.")


def main() -> int:
    try:
        client = HydraDB(token=get_api_key())
        ids = ingest_test_records(client)
        wait_for_ingestion(client, ids)
        result = query_fact_state(client)
        confirm_round_trip(result)
        return 0
    except Exception as exc:
        print(f"HydraDB round trip failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
