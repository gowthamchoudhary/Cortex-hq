"""Resolve candidate entities in HydraDB using conservative blocking and scoring."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any

from hydra_db import HydraDB


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


DATABASE_NAME = "hackhydra-track1"
PAGE_SIZE = 100
AUTO_MERGE_THRESHOLD = 0.85
PENDING_THRESHOLD = 0.60
VALID_TO_SENTINEL = 9_999_999_999
POLL_INTERVAL_SECONDS = 5
POLL_TIMEOUT_SECONDS = 300
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@([A-Z0-9.-]+\.[A-Z]{2,})\b", re.IGNORECASE)
USERNAME_RE = re.compile(r"(?<!\w)@[A-Z0-9._-]+", re.IGNORECASE)


@dataclass
class PairScore:
    entity_a_id: str
    entity_b_id: str
    name_similarity: float
    exact_id_match: bool
    graph_overlap: float
    combined_score: float


class UnionFind:
    def __init__(self, items: list[str]) -> None:
        self.parent = {item: item for item in items}

    def find(self, item: str) -> str:
        if self.parent[item] != item:
            self.parent[item] = self.find(self.parent[item])
        return self.parent[item]

    def union(self, left: str, right: str) -> None:
        root_left = self.find(left)
        root_right = self.find(right)
        if root_left != root_right:
            self.parent[root_right] = root_left

    def clusters(self) -> list[list[str]]:
        grouped: dict[str, list[str]] = defaultdict(list)
        for item in self.parent:
            grouped[self.find(item)].append(item)
        return [members for members in grouped.values() if len(members) > 1]


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
    payload = "|".join(str(part) for part in parts)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:24]


def list_all_sources(client: HydraDB, database: str, page_size: int = PAGE_SIZE) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    page = 1
    while True:
        response = client.context.list(
            database=database,
            type="knowledge",
            page=page,
            page_size=page_size,
        )
        data = to_plain_data(response.data)
        page_sources = data.get("sources") or []
        sources.extend(page_sources)
        pagination = data.get("pagination") or {}
        if not pagination.get("has_next"):
            break
        page += 1
    return sources


def metadata(source: dict[str, Any]) -> dict[str, Any]:
    return dict(source.get("metadata") or {})


def additional_metadata(source: dict[str, Any]) -> dict[str, Any]:
    return dict(source.get("additional_metadata") or {})


def get_source_doc_id(source: dict[str, Any]) -> str:
    return str(
        additional_metadata(source).get("source_doc_id")
        or metadata(source).get("source_doc_id")
        or ""
    )


def canonical_name(entity: dict[str, Any]) -> str:
    return str(metadata(entity).get("canonical_name") or entity.get("title") or entity.get("id") or "")


def first_token(name: str) -> str:
    return (name.strip().split() or [""])[0].lower()


def flatten_strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        items: list[str] = []
        for nested in value.values():
            items.extend(flatten_strings(nested))
        return items
    if isinstance(value, (list, tuple, set)):
        items = []
        for nested in value:
            items.extend(flatten_strings(nested))
        return items
    return [str(value)]


def aliases(entity: dict[str, Any]) -> list[str]:
    values = [canonical_name(entity)]
    extra = additional_metadata(entity)
    values.extend(flatten_strings(extra.get("aliases")))
    values.extend(flatten_strings(extra.get("alias")))
    return sorted({value.strip() for value in values if value and value.strip()})


def identifiers(entity: dict[str, Any]) -> set[str]:
    extra = additional_metadata(entity)
    values = flatten_strings(extra)
    found: set[str] = set()
    for value in values:
        for email in re.findall(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", value, re.IGNORECASE):
            found.add(email.lower())
        for username in USERNAME_RE.findall(value):
            found.add(username.lower())
    for key in ("email", "username", "user_id", "external_id"):
        value = extra.get(key)
        if value:
            found.add(str(value).lower())
    return found


def email_domains(entity: dict[str, Any]) -> set[str]:
    domains: set[str] = set()
    for value in flatten_strings(additional_metadata(entity)):
        domains.update(match.lower() for match in EMAIL_RE.findall(value))
    return domains


def block_entities(entities: list[dict[str, Any]]) -> list[set[str]]:
    block_map: dict[str, set[str]] = defaultdict(set)
    by_id = {entity["id"]: entity for entity in entities}
    for entity in entities:
        entity_id = entity["id"]
        name = canonical_name(entity)
        token = first_token(name)
        if token:
            block_map[f"name:{token}"].add(entity_id)

        for domain in email_domains(entity):
            block_map[f"email_domain:{domain}"].add(entity_id)

        source_doc_id = get_source_doc_id(entity)
        if source_doc_id:
            block_map[f"source_doc_id:{source_doc_id}"].add(entity_id)

    blocks = [ids for ids in block_map.values() if len(ids) > 1]
    seen_pairs: set[tuple[str, str]] = set()
    deduped_blocks: list[set[str]] = []
    for block in sorted(blocks, key=len):
        pairs = {tuple(sorted(pair)) for pair in combinations(block, 2)}
        new_pairs = pairs - seen_pairs
        if new_pairs:
            deduped_blocks.append({entity_id for pair in new_pairs for entity_id in pair if entity_id in by_id})
            seen_pairs.update(new_pairs)
    return deduped_blocks


def jaro_similarity(left: str, right: str) -> float:
    if left == right:
        return 1.0
    if not left or not right:
        return 0.0

    match_distance = max(0, max(len(left), len(right)) // 2 - 1)
    left_matches = [False] * len(left)
    right_matches = [False] * len(right)

    matches = 0
    for i, left_char in enumerate(left):
        start = max(0, i - match_distance)
        end = min(i + match_distance + 1, len(right))
        for j in range(start, end):
            if right_matches[j] or left_char != right[j]:
                continue
            left_matches[i] = True
            right_matches[j] = True
            matches += 1
            break

    if matches == 0:
        return 0.0

    transpositions = 0
    j = 0
    for i, left_match in enumerate(left_matches):
        if not left_match:
            continue
        while not right_matches[j]:
            j += 1
        if left[i] != right[j]:
            transpositions += 1
        j += 1

    return (
        matches / len(left)
        + matches / len(right)
        + (matches - transpositions / 2) / matches
    ) / 3


def jaro_winkler(left: str, right: str, prefix_scale: float = 0.1) -> float:
    left = left.lower().strip()
    right = right.lower().strip()
    jaro = jaro_similarity(left, right)
    prefix = 0
    for left_char, right_char in zip(left[:4], right[:4]):
        if left_char != right_char:
            break
        prefix += 1
    return jaro + prefix * prefix_scale * (1 - jaro)


def best_name_similarity(entity_a: dict[str, Any], entity_b: dict[str, Any]) -> float:
    return max(
        jaro_winkler(alias_a, alias_b)
        for alias_a in aliases(entity_a)
        for alias_b in aliases(entity_b)
    )


def fact_signature(fact: dict[str, Any]) -> tuple[str, str]:
    meta = metadata(fact)
    return str(meta.get("predicate") or ""), str(meta.get("source_doc_id") or "")


def fact_states_for_subject(client: HydraDB, database: str, subject_id: str) -> list[dict[str, Any]]:
    response = client.context.list(
        database=database,
        type="knowledge",
        filters={"metadata": {"type": "FactState", "subject_id": subject_id}},
        page_size=PAGE_SIZE,
    )
    data = to_plain_data(response.data)
    return list(data.get("sources") or [])


def graph_overlap(client: HydraDB, database: str, entity_a_id: str, entity_b_id: str) -> float:
    facts_a = {fact_signature(fact) for fact in fact_states_for_subject(client, database, entity_a_id)}
    facts_b = {fact_signature(fact) for fact in fact_states_for_subject(client, database, entity_b_id)}
    facts_a.discard(("", ""))
    facts_b.discard(("", ""))
    if not facts_a and not facts_b:
        return 0.0
    return len(facts_a & facts_b) / len(facts_a | facts_b)


def score_pair(client: HydraDB, database: str, entity_a: dict[str, Any], entity_b: dict[str, Any]) -> PairScore:
    exact_id_match = bool(identifiers(entity_a) & identifiers(entity_b))
    name_similarity = best_name_similarity(entity_a, entity_b)
    overlap = graph_overlap(client, database, entity_a["id"], entity_b["id"])
    combined_score = (0.6 if exact_id_match else 0.0) + 0.25 * name_similarity + 0.15 * overlap
    return PairScore(
        entity_a_id=entity_a["id"],
        entity_b_id=entity_b["id"],
        name_similarity=name_similarity,
        exact_id_match=exact_id_match,
        graph_overlap=overlap,
        combined_score=combined_score,
    )


def metadata_completeness(entity: dict[str, Any]) -> int:
    meta = metadata(entity)
    extra = additional_metadata(entity)
    score = sum(1 for value in meta.values() if value not in (None, "", [], {}))
    score += sum(1 for value in extra.values() if value not in (None, "", [], {}))
    score += len(aliases(entity))
    score += len(identifiers(entity)) * 2
    return score


def choose_canonical(cluster: list[str], entities_by_id: dict[str, dict[str, Any]]) -> str:
    return max(cluster, key=lambda entity_id: metadata_completeness(entities_by_id[entity_id]))


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


def mark_entity_resolved(client: HydraDB, database: str, entity: dict[str, Any], canonical_id: str, dry_run: bool) -> None:
    meta = metadata(entity)
    extra = additional_metadata(entity)
    meta["state"] = "resolved"
    extra["merged_into"] = canonical_id
    if not dry_run:
        update_source_metadata(client, database, entity["id"], meta, extra, entity.get("sub_tenant_id"))


def repoint_fact_state(client: HydraDB, database: str, fact: dict[str, Any], canonical_id: str, dry_run: bool) -> None:
    meta = metadata(fact)
    extra = additional_metadata(fact)
    meta["subject_id"] = canonical_id
    if not dry_run:
        update_source_metadata(client, database, fact["id"], meta, extra, fact.get("sub_tenant_id"))


def ingest_pending_merge(client: HydraDB, database: str, score: PairScore, entities_by_id: dict[str, dict[str, Any]], dry_run: bool) -> str:
    entity_a = entities_by_id[score.entity_a_id]
    entity_b = entities_by_id[score.entity_b_id]
    merge_id = f"candidate-merge-{stable_id(score.entity_a_id, score.entity_b_id)}"
    breakdown = {
        "entity_a_id": score.entity_a_id,
        "entity_b_id": score.entity_b_id,
        "entity_a_name": canonical_name(entity_a),
        "entity_b_name": canonical_name(entity_b),
        "name_similarity": score.name_similarity,
        "exact_id_match": score.exact_id_match,
        "graph_overlap": score.graph_overlap,
        "combined_score": score.combined_score,
    }
    app_knowledge = [
        {
            "id": merge_id,
            "database": database,
            "title": f"CandidateMerge: {canonical_name(entity_a)} <> {canonical_name(entity_b)}",
            "type": "candidate_merge",
            "content": {"text": json.dumps(breakdown, sort_keys=True)},
            "metadata": {
                "type": "CandidateMerge",
                "record_type": "CandidateMerge",
                "source_doc_id": f"{get_source_doc_id(entity_a)}|{get_source_doc_id(entity_b)}"[:256],
                "confidence": score.combined_score,
                "state": "pending",
            },
            "additional_metadata": breakdown,
        }
    ]
    graph_payload = {
        merge_id: {
            "entities": {
                score.entity_a_id: {
                    "name": canonical_name(entity_a),
                    "type": "ENTITY",
                    "namespace": "entities",
                    "external_id": score.entity_a_id,
                },
                score.entity_b_id: {
                    "name": canonical_name(entity_b),
                    "type": "ENTITY",
                    "namespace": "entities",
                    "external_id": score.entity_b_id,
                },
            },
            "relations": [
                {
                    "source": score.entity_a_id,
                    "target": score.entity_b_id,
                    "predicate": "PENDING_MERGE_WITH",
                    "context": json.dumps(breakdown, sort_keys=True),
                }
            ],
        }
    }
    if not dry_run:
        client.context.ingest(
            type="knowledge",
            database=database,
            upsert=True,
            app_knowledge=json.dumps(app_knowledge),
            graph_payload=json.dumps(graph_payload),
        )
    return merge_id


def apply_auto_merges(
    client: HydraDB,
    database: str,
    clusters: list[list[str]],
    entities_by_id: dict[str, dict[str, Any]],
    facts_by_subject: dict[str, list[dict[str, Any]]],
    dry_run: bool,
) -> int:
    merged_count = 0
    for cluster in clusters:
        canonical_id = choose_canonical(cluster, entities_by_id)
        for entity_id in cluster:
            if entity_id == canonical_id:
                continue
            mark_entity_resolved(client, database, entities_by_id[entity_id], canonical_id, dry_run)
            for fact in facts_by_subject.get(entity_id, []):
                repoint_fact_state(client, database, fact, canonical_id, dry_run)
            merged_count += 1
    return merged_count


def run_resolution(database: str, limit: int | None, dry_run: bool) -> dict[str, Any]:
    client = HydraDB(token=get_api_key())
    all_sources = list_all_sources(client, database)
    candidate_entities = [
        source
        for source in all_sources
        if metadata(source).get("type") == "Entity" and metadata(source).get("state") == "candidate"
    ]
    if limit is not None:
        candidate_entities = candidate_entities[:limit]

    fact_states = [source for source in all_sources if metadata(source).get("type") == "FactState"]
    facts_by_subject: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for fact in fact_states:
        subject_id = str(metadata(fact).get("subject_id") or "")
        if subject_id:
            facts_by_subject[subject_id].append(fact)

    entities_by_id = {entity["id"]: entity for entity in candidate_entities}
    blocks = block_entities(candidate_entities)
    union_find = UnionFind(list(entities_by_id))
    auto_merge_examples: list[PairScore] = []
    pending_examples: list[PairScore] = []
    compared_pairs: set[tuple[str, str]] = set()
    pending_count = 0

    for block in blocks:
        for entity_a_id, entity_b_id in combinations(sorted(block), 2):
            pair_key = tuple(sorted((entity_a_id, entity_b_id)))
            if pair_key in compared_pairs:
                continue
            compared_pairs.add(pair_key)

            score = score_pair(
                client,
                database,
                entities_by_id[entity_a_id],
                entities_by_id[entity_b_id],
            )
            if score.combined_score >= AUTO_MERGE_THRESHOLD:
                union_find.union(entity_a_id, entity_b_id)
                auto_merge_examples.append(score)
            elif score.combined_score >= PENDING_THRESHOLD:
                ingest_pending_merge(client, database, score, entities_by_id, dry_run)
                pending_examples.append(score)
                pending_count += 1

    clusters = union_find.clusters()
    auto_merged_count = apply_auto_merges(
        client,
        database,
        clusters,
        entities_by_id,
        facts_by_subject,
        dry_run,
    )

    return {
        "total_entities_processed": len(candidate_entities),
        "blocks": len(blocks),
        "pairs_compared": len(compared_pairs),
        "auto_merges_made": auto_merged_count,
        "pending_candidates_logged": pending_count,
        "example_merges": [score.__dict__ for score in auto_merge_examples[:3]],
        "example_pending": [score.__dict__ for score in pending_examples[:3]],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve candidate HydraDB entities.")
    parser.add_argument("--database", default=DATABASE_NAME)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--disabled", action="store_true")
    args = parser.parse_args()

    if args.disabled:
        print("Entity resolution disabled; candidate entities left unmerged.")
        return 0

    try:
        summary = run_resolution(args.database, args.limit, args.dry_run)
        print("Entity resolution summary:")
        print(f"- total entities processed: {summary['total_entities_processed']}")
        print(f"- blocks: {summary['blocks']}")
        print(f"- pairs compared: {summary['pairs_compared']}")
        print(f"- auto-merges made: {summary['auto_merges_made']}")
        print(f"- pending candidates logged: {summary['pending_candidates_logged']}")
        print("Example auto-merges:")
        print(json.dumps(summary["example_merges"], indent=2))
        print("Example pending candidates:")
        print(json.dumps(summary["example_pending"], indent=2))
        return 0
    except Exception as exc:
        print(f"Entity resolution failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
