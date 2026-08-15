"""Answer questions from the connected HydraDB graph with abstention."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import httpx
from hydra_db import HydraDB


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval.baseline import (  # noqa: E402
    DEFAULT_FIRE_FLIES_DIR,
    DEFAULT_GMAIL_DIR,
    build_doc_frequencies,
    load_documents,
    retrieve,
)
from resolution.entity_resolution import jaro_winkler  # noqa: E402


DATABASE_NAME = "hackhydra-track1"
PAGE_SIZE = 100
DEFAULT_MODEL = "llama-3.1-8b-instant"
GROQ_CHAT_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
OPENAI_CHAT_ENDPOINT = "https://api.openai.com/v1/chat/completions"
ENTITY_MATCH_THRESHOLD = 0.75
ABSTENTION_THRESHOLD = 0.4
CALIBRATION_PATH = PROJECT_ROOT / "reasoning" / "calibration.json"


@dataclass
class LinkResult:
    mention: str
    entity_id: str | None
    canonical_name: str | None
    score: float
    state: str
    no_anchor: bool
    fallback_used: bool = False


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


def calibrated_abstention_threshold(path: Path = CALIBRATION_PATH) -> float:
    if not path.exists():
        return ABSTENTION_THRESHOLD
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        threshold = float(data.get("recommended_threshold", ABSTENTION_THRESHOLD))
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return ABSTENTION_THRESHOLD
    return max(0.0, min(1.0, threshold))


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


def provider_config(provider: str, model: str | None) -> tuple[str, str, str]:
    if provider == "auto":
        provider = "groq" if os.environ.get("GROQ_API_KEY") else "openai"

    if provider == "groq":
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY is required.")
        return GROQ_CHAT_ENDPOINT, api_key, model or os.environ.get("GROQ_MODEL", DEFAULT_MODEL)

    if provider == "openai":
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required.")
        return OPENAI_CHAT_ENDPOINT, api_key, model or os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")

    raise ValueError(f"Unsupported provider: {provider}")


def call_llm_json(
    messages: list[dict[str, str]],
    provider: str,
    model: str | None,
    timeout_seconds: int,
    retries: int = 2,
) -> dict[str, Any]:
    endpoint, api_key, resolved_model = provider_config(provider, model)
    body = {
        "model": resolved_model,
        "messages": messages,
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    try:
        response = httpx.post(
            endpoint,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "cortex-hydradb-answerer/0.1",
            },
            json=body,
            timeout=timeout_seconds,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 429 and retries > 0:
            time.sleep(4)
            return call_llm_json(messages, provider, model, timeout_seconds, retries - 1)
        raise RuntimeError(f"LLM API returned HTTP {exc.response.status_code}: {exc.response.text}") from exc

    return json.loads(response.json()["choices"][0]["message"]["content"])


def query_understanding(question: str, provider: str, model: str | None, timeout_seconds: int) -> dict[str, Any]:
    messages = [
        {
            "role": "system",
            "content": (
                "Extract query understanding as JSON only. Return keys: "
                "target_entity_mentions as an array of strings, intent as one of "
                "lookup, causal, temporal, completeness, and time_scope as current or historical."
            ),
        },
        {"role": "user", "content": question},
    ]
    result = call_llm_json(messages, provider, model, timeout_seconds)
    intent = str(result.get("intent") or "lookup").lower()
    if intent not in {"lookup", "causal", "temporal", "completeness"}:
        intent = "lookup"
    time_scope = str(result.get("time_scope") or "current").lower()
    if time_scope not in {"current", "historical"}:
        time_scope = "historical" if intent == "temporal" else "current"
    mentions = [str(item).strip() for item in result.get("target_entity_mentions", []) if str(item).strip()]
    return {"target_entity_mentions": mentions, "intent": intent, "time_scope": time_scope}


def metadata(source: dict[str, Any]) -> dict[str, Any]:
    return dict(source.get("metadata") or {})


def additional_metadata(source: dict[str, Any]) -> dict[str, Any]:
    return dict(source.get("additional_metadata") or {})


def list_all_sources(client: HydraDB, database: str, collection: str) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    page = 1
    while True:
        response = client.context.list(database=database, collection=collection, type="knowledge", page=page, page_size=PAGE_SIZE)
        data = to_plain_data(response.data)
        sources.extend(data.get("sources") or [])
        pagination = data.get("pagination") or {}
        if not pagination.get("has_next"):
            break
        page += 1
    return sources


def flatten_strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        values: list[str] = []
        for nested in value.values():
            values.extend(flatten_strings(nested))
        return values
    if isinstance(value, (list, tuple, set)):
        values = []
        for nested in value:
            values.extend(flatten_strings(nested))
        return values
    return [str(value)]


def canonical_name(entity: dict[str, Any]) -> str:
    return str(metadata(entity).get("canonical_name") or entity.get("title") or entity.get("id") or "")


def entity_aliases(entity: dict[str, Any]) -> list[str]:
    extra = additional_metadata(entity)
    values = [canonical_name(entity)]
    values.extend(flatten_strings(extra.get("aliases")))
    values.extend(flatten_strings(extra.get("alias")))
    return [value for value in {item.strip() for item in values if item and item.strip()}]


def score_entity_mention(mention: str, entity: dict[str, Any]) -> float:
    return max((jaro_winkler(mention, alias) for alias in entity_aliases(entity)), default=0.0)


def link_entity_mentions(mentions: list[str], entities: list[dict[str, Any]]) -> list[LinkResult]:
    links: list[LinkResult] = []
    for mention in mentions:
        scored = sorted(
            ((entity, score_entity_mention(mention, entity)) for entity in entities),
            key=lambda item: item[1],
            reverse=True,
        )
        if not scored or scored[0][1] < ENTITY_MATCH_THRESHOLD:
            links.append(LinkResult(mention, None, None, 0.0, "no_anchor", True))
            continue
        entity, score = scored[0]
        links.append(
            LinkResult(
                mention=mention,
                entity_id=entity["id"],
                canonical_name=canonical_name(entity),
                score=score,
                state=str(metadata(entity).get("state") or "candidate"),
                no_anchor=False,
            )
        )
    return links


def fact_value(fact: dict[str, Any]) -> str:
    extra = additional_metadata(fact)
    if "value" in extra:
        return str(extra.get("value") or "")
    return str(metadata(fact).get("value") or fact.get("title") or "")


def source_doc_id(source: dict[str, Any]) -> str:
    return str(metadata(source).get("source_doc_id") or additional_metadata(source).get("source_doc_id") or "")


def fact_sort_key(fact: dict[str, Any]) -> int:
    value = metadata(fact).get("valid_from")
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def relation_triplets(client: HydraDB, database: str, collection: str, entity_id: str, limit: int = 50) -> list[dict[str, Any]]:
    try:
        response = client.context.relations(database=database, collection=collection, id=entity_id, type="knowledge", limit=limit)
    except Exception:
        return []
    data = to_plain_data(response.data)
    relations = data.get("relations") or data.get("triplets") or data.get("chunk_relations") or []
    triplets: list[dict[str, Any]] = []
    for item in relations:
        if "triplets" in item:
            triplets.extend(item.get("triplets") or [])
        elif "relations" in item:
            for relation in item.get("relations") or []:
                relation_item = dict(item)
                relation_item.pop("relations", None)
                relation_item["relation"] = relation
                triplets.append(relation_item)
        else:
            triplets.append(item)
    return triplets


def relation_entities(triplet: dict[str, Any]) -> tuple[str | None, str | None]:
    relation = triplet.get("relation") or triplet
    source_id = relation.get("source_entity_id") or relation.get("source") or triplet.get("source")
    target_id = relation.get("target_entity_id") or relation.get("target") or triplet.get("target")
    return relation_entity_id(source_id), relation_entity_id(target_id)


def relation_entity_id(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("entity_id", "external_id", "id"):
            if value.get(key):
                return str(value[key])
    return str(value)


def relation_predicate(triplet: dict[str, Any]) -> str:
    relation = triplet.get("relation") or triplet
    return str(relation.get("canonical_predicate") or relation.get("raw_predicate") or relation.get("predicate") or "")


def is_bookkeeping_relation(predicate: str) -> bool:
    return predicate.strip().upper() == "HAS_STATE"


def expand_subgraph(
    client: HydraDB,
    database: str,
    collection: str,
    links: list[LinkResult],
    all_sources: list[dict[str, Any]],
    time_scope: str,
    hops: int,
) -> dict[str, Any]:
    entities_by_id = {source["id"]: source for source in all_sources if metadata(source).get("type") == "Entity"}
    fact_states = [source for source in all_sources if metadata(source).get("type") == "FactState"]
    facts_by_subject: dict[str, list[dict[str, Any]]] = {}
    for fact in fact_states:
        # FactState validity is independent of whether its entity is a candidate or resolved.
        subject_id = str(metadata(fact).get("subject_id") or "")
        facts_by_subject.setdefault(subject_id, []).append(fact)

    frontier = [link.entity_id for link in links if link.entity_id]
    visited = set(frontier)
    relations: list[dict[str, Any]] = []
    for _ in range(max(hops, 0)):
        next_frontier: list[str] = []
        for entity_id in frontier:
            for triplet in relation_triplets(client, database, collection, entity_id):
                source_id, target_id = relation_entities(triplet)
                predicate = relation_predicate(triplet)
                if is_bookkeeping_relation(predicate):
                    continue
                relations.append(
                    {
                        "source_entity_id": source_id,
                        "target_entity_id": target_id,
                        "predicate": predicate,
                        "source_doc_id": source_doc_id(triplet),
                        "raw": triplet,
                    }
                )
                for candidate_id in (source_id, target_id):
                    if candidate_id and candidate_id not in visited:
                        visited.add(candidate_id)
                        next_frontier.append(candidate_id)
        frontier = next_frontier

    facts: list[dict[str, Any]] = []
    for entity_id in visited:
        for fact in facts_by_subject.get(entity_id, []):
            state = str(metadata(fact).get("state") or "")
            if state == "current" or (time_scope == "historical" and state in {"current", "superseded"}):
                facts.append(fact)
    facts = sorted(facts, key=fact_sort_key)

    return {
        "entities": [entities_by_id[entity_id] for entity_id in visited if entity_id in entities_by_id],
        "facts": facts,
        "relations": relations,
    }


def fallback_links(question: str, entities: list[dict[str, Any]]) -> tuple[list[LinkResult], list[str]]:
    documents = load_documents([("fireflies", DEFAULT_FIRE_FLIES_DIR), ("gmail", DEFAULT_GMAIL_DIR)])
    doc_frequencies = build_doc_frequencies(documents)
    retrieved = retrieve(question, documents, doc_frequencies, top_k=5)
    retrieved_doc_ids = [document.source_id for document, _ in retrieved]
    candidate_entities = [
        entity for entity in entities if source_doc_id(entity) in set(retrieved_doc_ids)
    ]
    if not candidate_entities:
        return [], retrieved_doc_ids
    query_tokens = " ".join(re.findall(r"[A-Za-z0-9]+", question))
    best = max(candidate_entities, key=lambda entity: score_entity_mention(query_tokens, entity))
    return [
        LinkResult(
            mention=query_tokens,
            entity_id=best["id"],
            canonical_name=canonical_name(best),
            score=max(score_entity_mention(query_tokens, best) * 0.8, 0.4),
            state=str(metadata(best).get("state") or "candidate"),
            no_anchor=False,
            fallback_used=True,
        )
    ], retrieved_doc_ids


def fallback_documents(question: str) -> tuple[list[dict[str, Any]], list[str]]:
    documents = load_documents([("fireflies", DEFAULT_FIRE_FLIES_DIR), ("gmail", DEFAULT_GMAIL_DIR)])
    doc_frequencies = build_doc_frequencies(documents)
    retrieved = retrieve(question, documents, doc_frequencies, top_k=5)
    docs = [
        {
            "source_id": document.source_id,
            "source": document.source,
            "timestamp": document.timestamp,
            "content": document.content[:2500],
            "score": score,
        }
        for document, score in retrieved
    ]
    return docs, [doc["source_id"] for doc in docs]


def compute_confidence(links: list[LinkResult], subgraph: dict[str, Any]) -> tuple[float, dict[str, Any]]:
    facts = subgraph["facts"]
    relations = subgraph["relations"]
    evidence = {source_doc_id(fact) for fact in facts if source_doc_id(fact)}
    evidence.update(rel.get("source_doc_id") for rel in relations if rel.get("source_doc_id"))
    disputed = [fact for fact in facts if metadata(fact).get("state") == "disputed"]
    link_scores = [link.score for link in links if not link.no_anchor]
    avg_link = sum(link_scores) / len(link_scores) if link_scores else 0.0
    fallback_used = any(link.fallback_used for link in links)

    subgraph_score = min((len(facts) + len(relations)) / 10, 1.0) * 0.35
    evidence_score = min(len(evidence) / 5, 1.0) * 0.25
    link_score = avg_link * 0.30
    penalty = (0.25 if disputed else 0.0) + (0.15 if fallback_used else 0.0)
    confidence = max(0.0, min(1.0, subgraph_score + evidence_score + link_score - penalty))
    return confidence, {
        "subgraph_score": subgraph_score,
        "evidence_score": evidence_score,
        "link_score": link_score,
        "disputed_penalty": 0.25 if disputed else 0.0,
        "fallback_penalty": 0.15 if fallback_used else 0.0,
        "facts": len(facts),
        "relations": len(relations),
        "evidence_count": len(evidence),
        "avg_entity_link_score": avg_link,
    }


def context_packet(question: str, links: list[LinkResult], subgraph: dict[str, Any], confidence: float) -> dict[str, Any]:
    facts = []
    for fact in subgraph["facts"]:
        meta = metadata(fact)
        facts.append(
            {
                "id": fact["id"],
                "subject_id": meta.get("subject_id"),
                "predicate": meta.get("predicate"),
                "value": fact_value(fact),
                "state": meta.get("state"),
                "valid_from": meta.get("valid_from"),
                "source_doc_id": source_doc_id(fact),
            }
        )
    entities = [
        {
            "id": entity["id"],
            "canonical_name": canonical_name(entity),
            "entity_type": metadata(entity).get("entity_type"),
            "state": metadata(entity).get("state"),
            "source_doc_id": source_doc_id(entity),
        }
        for entity in subgraph["entities"]
    ]
    relations = [
        relation
        for relation in subgraph["relations"]
        if not is_bookkeeping_relation(str(relation.get("predicate") or ""))
    ]
    return {
        "question": question,
        "resolved_entities": [asdict(link) for link in links],
        "current_state": facts,
        "entities": entities,
        "relations": relations,
        "fallback_documents": subgraph.get("fallback_documents", []),
        "evidence_doc_ids": sorted({fact["source_doc_id"] for fact in facts if fact["source_doc_id"]}),
        "confidence": confidence,
    }


def generate_answer(packet: dict[str, Any], provider: str, model: str | None, timeout_seconds: int) -> str:
    messages = [
        {
            "role": "system",
            "content": (
                "Using ONLY the provided context, answer the question and cite which "
                "evidence supports each part of your answer. Do not add information "
                "not present in the context. Return JSON exactly like {\"answer\":\"...\"}."
            ),
        },
        {"role": "user", "content": json.dumps(packet, sort_keys=True)},
    ]
    result = call_llm_json(messages, provider, model, timeout_seconds)
    return str(result.get("answer") or "").strip() or "I couldn't find sufficient evidence in the connected data to answer this."


def answer_question(
    question: str,
    database: str,
    collection: str,
    provider: str,
    model: str | None,
    timeout_seconds: int,
    verbose: bool,
    disable_abstention: bool = False,
    disable_graph_reasoning: bool = False,
) -> dict[str, Any]:
    load_dotenv()
    client = HydraDB(token=get_api_key())
    understanding = query_understanding(question, provider, model, timeout_seconds)
    all_sources = list_all_sources(client, database, collection)
    entities = [source for source in all_sources if metadata(source).get("type") == "Entity"]
    mentions = understanding["target_entity_mentions"] or [question]
    links = link_entity_mentions(mentions, entities)
    fallback_doc_ids: list[str] = []
    fallback_context: list[dict[str, Any]] = []

    if disable_graph_reasoning:
        fallback_context, fallback_doc_ids = fallback_documents(question)
        fallback, _ = fallback_links(question, entities)
        if fallback:
            links = fallback
        subgraph = {
            "entities": [],
            "facts": [],
            "relations": [],
            "fallback_documents": fallback_context,
        }
    elif all(link.no_anchor for link in links):
        fallback, fallback_doc_ids = fallback_links(question, entities)
        if fallback:
            links = fallback
        subgraph = expand_subgraph(
            client,
            database,
            collection,
            links,
            all_sources,
            understanding["time_scope"],
            hops=2,
        )
    else:
        subgraph = expand_subgraph(
            client,
            database,
            collection,
            links,
            all_sources,
            understanding["time_scope"],
            hops=2,
        )
    confidence, breakdown = compute_confidence(links, subgraph)
    packet = context_packet(question, links, subgraph, confidence)
    evidence = packet["evidence_doc_ids"] or fallback_doc_ids
    abstention_threshold = calibrated_abstention_threshold()

    if not disable_abstention and (confidence < abstention_threshold or not subgraph["facts"]):
        result = {
            "answer": "I couldn't find sufficient evidence in the connected data to answer this.",
            "evidence": [],
            "confidence": confidence,
            "abstained": True,
        }
    else:
        result = {
            "answer": generate_answer(packet, provider, model, timeout_seconds),
            "evidence": evidence,
            "confidence": confidence,
            "abstained": False,
        }

    if verbose:
        result["debug"] = {
            "query_understanding": understanding,
            "links": [asdict(link) for link in links],
            "confidence_breakdown": breakdown,
            "abstention_threshold": abstention_threshold,
            "context_packet": packet,
            "disable_abstention": disable_abstention,
            "disable_graph_reasoning": disable_graph_reasoning,
        }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Answer a question from the HydraDB graph.")
    parser.add_argument("question")
    parser.add_argument("--database", default=DATABASE_NAME)
    parser.add_argument("--collection", default="default")
    parser.add_argument("--provider", choices=("auto", "groq", "openai"), default="auto")
    parser.add_argument("--model", default=None)
    parser.add_argument("--timeout-seconds", type=int, default=90)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--disable-abstention", action="store_true")
    parser.add_argument("--disable-graph-reasoning", action="store_true")
    args = parser.parse_args()

    try:
        result = answer_question(
            question=args.question,
            database=args.database,
            collection=args.collection,
            provider=args.provider,
            model=args.model,
            timeout_seconds=args.timeout_seconds,
            verbose=args.verbose,
            disable_abstention=args.disable_abstention,
            disable_graph_reasoning=args.disable_graph_reasoning,
        )
        print(json.dumps(result, indent=2))
        return 0
    except Exception as exc:
        print(f"Question answering failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
