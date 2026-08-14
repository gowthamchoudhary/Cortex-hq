"""Ensure a named HydraDB collection exists for this project."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from hydra_db import HydraDB


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DATABASE_NAME = "hackhydra-track1"


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


def collection_names(client: HydraDB, database: str) -> set[str]:
    response = client.databases.collections(database=database)
    data = to_plain_data(response.data)
    if isinstance(data, dict):
        collections = data.get("collections") or data.get("items") or []
    else:
        collections = data or []

    names: set[str] = set()
    for item in collections:
        if isinstance(item, str):
            names.add(item)
        elif isinstance(item, dict):
            name = item.get("name") or item.get("collection")
            if name:
                names.add(str(name))
    return names


def ensure_collection(client: HydraDB, database: str, collection: str) -> bool:
    if collection in collection_names(client, database):
        print(f"Collection '{collection}' already exists")
        return False

    marker_id = "__collection_init__"
    app_knowledge = [
        {
            "id": marker_id,
            "database": database,
            "title": "Collection initialization marker",
            "type": "entity",
            "content": {"text": f"System marker for collection '{collection}'."},
            "metadata": {
                "type": "Entity",
                "canonical_name": marker_id,
                "state": "system",
            },
            "additional_metadata": {"system_marker": True},
        }
    ]
    graph_payload = {
        marker_id: {
            "entities": {},
            "relations": [],
        }
    }
    client.context.ingest(
        type="knowledge",
        database=database,
        collection=collection,
        upsert=True,
        app_knowledge=json.dumps(app_knowledge),
        graph_payload=json.dumps(graph_payload),
    )
    print(f"Collection '{collection}' ready")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collection", required=True, help="Collection name to ensure")
    args = parser.parse_args()

    try:
        client = HydraDB(token=get_api_key())
        ensure_collection(client, DATABASE_NAME, args.collection)
        return 0
    except Exception as exc:
        print(f"Failed to ensure collection: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())