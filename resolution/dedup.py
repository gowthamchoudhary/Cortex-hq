"""Detect and mark near-duplicate documents with MinHash LSH."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from datasketch import MinHash, MinHashLSH
from hydra_db import HydraDB


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval.baseline import DEFAULT_FIRE_FLIES_DIR, DEFAULT_GMAIL_DIR, load_documents  # noqa: E402


DATABASE_NAME = "hackhydra-track1"
PAGE_SIZE = 100
NUM_PERM = 128
SHINGLE_SIZE = 5
LSH_THRESHOLD = 0.8


@dataclass
class DocumentRecord:
    id: str
    source: str
    timestamp: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    additional_metadata: dict[str, Any] = field(default_factory=dict)
    hydradb_source: dict[str, Any] | None = None


@dataclass
class ClusterExample:
    canonical_id: str
    duplicate_ids: list[str]
    pair_scores: dict[str, float]


class UnionFind:
    def __init__(self, ids: list[str]) -> None:
        self.parent = {item: item for item in ids}

    def find(self, item: str) -> str:
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, left: str, right: str) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root

    def clusters(self) -> list[list[str]]:
        grouped: dict[str, list[str]] = {}
        for item in self.parent:
            grouped.setdefault(self.find(item), []).append(item)
        return [cluster for cluster in grouped.values() if len(cluster) > 1]


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


def metadata(source: dict[str, Any]) -> dict[str, Any]:
    return dict(source.get("metadata") or {})


def additional_metadata(source: dict[str, Any]) -> dict[str, Any]:
    return dict(source.get("additional_metadata") or {})


def list_all_sources(client: HydraDB, database: str, collection: str, page_size: int = PAGE_SIZE) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    page = 1
    while True:
        response = client.context.list(
            database=database,
            collection=collection,
            type="knowledge",
            page=page,
            page_size=page_size,
        )
        data = to_plain_data(response.data)
        sources.extend(data.get("sources") or [])
        pagination = data.get("pagination") or {}
        if not pagination.get("has_next"):
            break
        page += 1
    return sources


def update_source_metadata(
    client: HydraDB,
    database: str,
    source_id: str,
    meta: dict[str, Any],
    extra: dict[str, Any],
    collection: str | None,
) -> None:
    try:
        client.context.update_source_metadata(
            source_id,
            database=database,
            collection=collection,
            database_metadata=meta,
            additional_metadata=extra,
        )
    except Exception:
        client.context.update_source_metadata(
            source_id,
            database=database,
            collection=collection,
            tenant_metadata=meta,
            additional_metadata=extra,
        )


def hydradb_documents(client: HydraDB, database: str, collection: str) -> list[DocumentRecord]:
    docs: list[DocumentRecord] = []
    for source in list_all_sources(client, database, collection):
        meta = metadata(source)
        record_type = str(meta.get("type") or meta.get("record_type") or "").lower()
        if record_type != "document":
            continue
        docs.append(
            DocumentRecord(
                id=str(source.get("id") or meta.get("source_doc_id") or ""),
                source=str(meta.get("doc_source_type") or meta.get("source") or ""),
                timestamp=str(meta.get("timestamp") or source.get("created_at") or ""),
                content=str(source.get("content") or source.get("note") or source.get("title") or ""),
                metadata=meta,
                additional_metadata=additional_metadata(source),
                hydradb_source=source,
            )
        )
    return [doc for doc in docs if doc.id and doc.content.strip()]


def local_documents() -> list[DocumentRecord]:
    raw_docs = load_documents([("fireflies", DEFAULT_FIRE_FLIES_DIR), ("gmail", DEFAULT_GMAIL_DIR)])
    docs = []
    for raw in raw_docs:
        docs.append(
            DocumentRecord(
                id=raw.source_id,
                source=raw.source,
                timestamp=raw.timestamp,
                content=raw.content,
                metadata=dict(raw.metadata or {}),
                additional_metadata={},
                hydradb_source=None,
            )
        )
    return [doc for doc in docs if doc.id and doc.content.strip()]


def load_source_documents(database: str, collection: str, source: str) -> tuple[list[DocumentRecord], str, HydraDB | None]:
    if source == "local":
        return local_documents(), "local", None
    try:
        client = HydraDB(token=get_api_key())
        docs = hydradb_documents(client, database, collection)
        if docs:
            return docs, "hydradb", client
        if source == "hydradb":
            return [], "hydradb", client
        print("No HydraDB Document records found; falling back to local Fireflies + Gmail normalized documents.")
        return local_documents(), "local", client
    except Exception as exc:
        if source == "hydradb":
            raise
        print(f"Could not load HydraDB Document records ({exc}); falling back to local documents.")
        return local_documents(), "local", None


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def shingles(text: str, size: int = SHINGLE_SIZE) -> set[str]:
    tokens = tokenize(text)
    if not tokens:
        return set()
    if len(tokens) < size:
        return {" ".join(tokens)}
    return {" ".join(tokens[index : index + size]) for index in range(len(tokens) - size + 1)}


def minhash(text: str) -> MinHash:
    signature = MinHash(num_perm=NUM_PERM)
    doc_shingles = shingles(text)
    if not doc_shingles:
        signature.update(b"")
        return signature
    for shingle in doc_shingles:
        signature.update(shingle.encode("utf-8"))
    return signature


def metadata_completeness(doc: DocumentRecord) -> int:
    values: list[Any] = [doc.source, doc.timestamp, doc.content]
    values.extend(doc.metadata.values())
    values.extend(doc.additional_metadata.values())
    return sum(1 for value in values if value not in (None, "", [], {}))


def timestamp_sort_value(timestamp: str) -> int:
    numbers = re.findall(r"\d+", str(timestamp or ""))
    if not numbers:
        return 0
    joined = "".join(numbers[:6])
    try:
        return int(joined)
    except ValueError:
        return 0


def pick_canonical(cluster: list[str], docs_by_id: dict[str, DocumentRecord]) -> DocumentRecord:
    return max(
        (docs_by_id[doc_id] for doc_id in cluster),
        key=lambda doc: (metadata_completeness(doc), timestamp_sort_value(doc.timestamp), len(doc.content)),
    )


def find_near_duplicate_clusters(docs: list[DocumentRecord]) -> tuple[list[list[str]], dict[tuple[str, str], float]]:
    signatures = {doc.id: minhash(doc.content) for doc in docs}
    lsh = MinHashLSH(threshold=LSH_THRESHOLD, num_perm=NUM_PERM)
    union_find = UnionFind([doc.id for doc in docs])
    pair_scores: dict[tuple[str, str], float] = {}

    for doc in docs:
        signature = signatures[doc.id]
        for candidate_id in lsh.query(signature):
            pair = tuple(sorted((doc.id, candidate_id)))
            if pair[0] == pair[1] or pair in pair_scores:
                continue
            score = signatures[pair[0]].jaccard(signatures[pair[1]])
            if score >= LSH_THRESHOLD:
                pair_scores[pair] = score
                union_find.union(pair[0], pair[1])
        lsh.insert(doc.id, signature)

    return union_find.clusters(), pair_scores


def mark_duplicates(
    client: HydraDB | None,
    database: str,
    source: str,
    cluster: list[str],
    canonical: DocumentRecord,
    docs_by_id: dict[str, DocumentRecord],
    dry_run: bool,
    collection: str,
) -> int:
    marked = 0
    for doc_id in cluster:
        doc = docs_by_id[doc_id]
        is_canonical = doc.id == canonical.id
        doc.metadata["is_canonical"] = is_canonical
        if is_canonical:
            doc.additional_metadata.pop("near_duplicate_of", None)
        else:
            doc.additional_metadata["near_duplicate_of"] = canonical.id
            marked += 1

        if source == "hydradb" and client and doc.hydradb_source and not dry_run:
            update_source_metadata(
                client,
                database,
                doc.id,
                doc.metadata,
                doc.additional_metadata,
                collection,
            )
    return marked


def save_local_marks(path: Path, docs: list[DocumentRecord]) -> None:
    marked_docs = [
        {
            "id": doc.id,
            "source": doc.source,
            "timestamp": doc.timestamp,
            "is_canonical": doc.metadata.get("is_canonical", True),
            "near_duplicate_of": doc.additional_metadata.get("near_duplicate_of"),
        }
        for doc in docs
        if doc.metadata.get("is_canonical") is not None or doc.additional_metadata.get("near_duplicate_of")
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(marked_docs, indent=2), encoding="utf-8")


def run_dedup(database: str, collection: str, limit: int | None, dry_run: bool, source: str, output: Path) -> dict[str, Any]:
    docs, document_source, client = load_source_documents(database, collection, source)
    if limit is not None:
        docs = docs[:limit]

    docs_by_id = {doc.id: doc for doc in docs}
    clusters, pair_scores = find_near_duplicate_clusters(docs)
    examples: list[ClusterExample] = []
    marked = 0

    for cluster in clusters:
        canonical = pick_canonical(cluster, docs_by_id)
        marked += mark_duplicates(client, database, document_source, cluster, canonical, docs_by_id, dry_run, collection)
        cluster_scores = {
            f"{left} <> {right}": score
            for (left, right), score in pair_scores.items()
            if left in cluster and right in cluster
        }
        examples.append(
            ClusterExample(
                canonical_id=canonical.id,
                duplicate_ids=sorted(doc_id for doc_id in cluster if doc_id != canonical.id),
                pair_scores=cluster_scores,
            )
        )

    if document_source == "local" and not dry_run:
        save_local_marks(output, docs)

    return {
        "document_source": document_source,
        "total_docs_processed": len(docs),
        "near_duplicate_clusters_found": len(clusters),
        "docs_marked_non_canonical": marked,
        "dry_run": dry_run,
        "local_marks_output": str(output) if document_source == "local" and not dry_run else None,
        "examples": [asdict(example) for example in examples[:3]],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Detect and mark near-duplicate documents.")
    parser.add_argument("--database", default=DATABASE_NAME)
    parser.add_argument("--collection", default="default")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--source", choices=("local", "hydradb"), default="local")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "resolution" / "results" / "dedup_marks.json")
    args = parser.parse_args()

    try:
        summary = run_dedup(args.database, args.collection, args.limit, args.dry_run, args.source, args.output)
        print("Near-duplicate document detection summary:")
        print(f"- source of truth: {summary['document_source']}")
        print(f"- total docs processed: {summary['total_docs_processed']}")
        print(f"- near-duplicate clusters found: {summary['near_duplicate_clusters_found']}")
        print(f"- docs marked non-canonical: {summary['docs_marked_non_canonical']}")
        print(f"- dry run: {summary['dry_run']}")
        if summary["local_marks_output"]:
            print(f"- local marks saved to: {summary['local_marks_output']}")
        print("Example clusters:")
        print(json.dumps(summary["examples"], indent=2))
        return 0
    except Exception as exc:
        print(f"Dedup failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
