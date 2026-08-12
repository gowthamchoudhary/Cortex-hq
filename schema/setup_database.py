"""Create or fetch the HydraDB database used by this project."""

import os
import sys

from hydra_db import ConflictError, HydraDB


DATABASE_NAME = "hackhydra-track1"

DATABASE_METADATA_SCHEMA = [
    {"name": "type", "data_type": "VARCHAR", "max_length": 256, "enable_match": True},
    {"name": "entity_type", "data_type": "VARCHAR", "max_length": 256, "enable_match": True},
    {"name": "canonical_name", "data_type": "VARCHAR", "max_length": 512, "enable_match": True},
    {"name": "subject_id", "data_type": "VARCHAR", "max_length": 256, "enable_match": True},
    {"name": "predicate", "data_type": "VARCHAR", "max_length": 256, "enable_match": True},
    {"name": "source_doc_id", "data_type": "VARCHAR", "max_length": 256, "enable_match": True},
    {"name": "valid_from", "data_type": "INT64"},
    {"name": "valid_to", "data_type": "INT64"},
    {"name": "txn_from", "data_type": "INT64"},
    {"name": "txn_to", "data_type": "INT64"},
    {"name": "authority_weight", "data_type": "FLOAT"},
    {"name": "corroboration_count", "data_type": "INT32"},
    {"name": "confidence", "data_type": "FLOAT"},
    {"name": "state", "data_type": "VARCHAR", "max_length": 256, "enable_match": True},
]


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


def fetch_existing_database(client: HydraDB) -> None:
    response = client.databases.list()
    databases = getattr(response.data, "databases", [])

    if DATABASE_NAME not in databases:
        raise RuntimeError(
            f'Database "{DATABASE_NAME}" already exists but was not returned by list().'
        )

    print(f'Database "{DATABASE_NAME}" already exists; fetched existing database.')


def create_database(client: HydraDB) -> None:
    try:
        client.databases.create(
            database=DATABASE_NAME,
            database_metadata_schema=DATABASE_METADATA_SCHEMA,
        )
        print(f'Database "{DATABASE_NAME}" creation requested successfully.')
    except ConflictError:
        fetch_existing_database(client)


def main() -> int:
    try:
        client = HydraDB(token=get_api_key())
        create_database(client)
        return 0
    except Exception as exc:
        print(f"Failed to set up HydraDB database: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
