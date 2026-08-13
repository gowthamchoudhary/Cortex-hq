"""Minimal Streamlit explorer for the HydraDB knowledge graph."""

from __future__ import annotations

import os
import sys
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from urllib.parse import quote

import streamlit as st
from hydra_db import HydraDB


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DATABASE_NAME = "hackhydra-track1"
PAGE_SIZE = 100


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


def aliases(entity: dict[str, Any]) -> list[str]:
    extra = additional_metadata(entity)
    values = flatten_strings(extra.get("aliases")) + flatten_strings(extra.get("alias"))
    return sorted({value.strip() for value in values if value and value.strip()})


def source_doc_id(source: dict[str, Any]) -> str:
    return str(metadata(source).get("source_doc_id") or additional_metadata(source).get("source_doc_id") or "")


def fact_value(fact: dict[str, Any]) -> str:
    extra = additional_metadata(fact)
    if "value" in extra:
        return str(extra.get("value") or "")
    meta = metadata(fact)
    return str(meta.get("value") or fact.get("note") or fact.get("title") or "")


def valid_from(fact: dict[str, Any]) -> int:
    try:
        return int(float(metadata(fact).get("valid_from") or 0))
    except (TypeError, ValueError):
        return 0


def list_all_sources(client: HydraDB, database: str) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    page = 1
    while True:
        response = client.context.list(database=database, type="knowledge", page=page, page_size=PAGE_SIZE)
        data = to_plain_data(response.data)
        sources.extend(data.get("sources") or [])
        pagination = data.get("pagination") or {}
        if not pagination.get("has_next"):
            break
        page += 1
    return sources


@st.cache_data(ttl=60)
def cached_sources(database: str, api_key: str) -> list[dict[str, Any]]:
    client = HydraDB(token=api_key)
    return list_all_sources(client, database)


def entity_terms(entity: dict[str, Any]) -> list[str]:
    terms = [str(entity.get("id") or ""), canonical_name(entity), *aliases(entity)]
    return [term.strip() for term in terms if term and term.strip()]


def resolve_entity(query: str, entities: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, float]:
    needle = query.strip().lower()
    if not needle:
        return None, 0.0

    for entity in entities:
        if str(entity.get("id") or "").lower() == needle:
            return entity, 1.0

    scored: list[tuple[float, dict[str, Any]]] = []
    for entity in entities:
        best = 0.0
        for term in entity_terms(entity):
            haystack = term.lower()
            score = 1.0 if haystack == needle else SequenceMatcher(None, needle, haystack).ratio()
            if needle in haystack or haystack in needle:
                score = max(score, 0.85)
            best = max(best, score)
        scored.append((best, entity))

    score, entity = max(scored, key=lambda item: item[0], default=(0.0, None))
    return (entity, score) if entity and score >= 0.6 else (None, score)


def fact_rows(facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for fact in facts:
        meta = metadata(fact)
        rows.append(
            {
                "predicate": meta.get("predicate"),
                "value": fact_value(fact),
                "source_doc_id": source_doc_id(fact),
                "authority_weight": meta.get("authority_weight"),
                "valid_from": meta.get("valid_from"),
            }
        )
    return rows


def relation_triplets(client: HydraDB, database: str, entity_id: str, limit: int = 50) -> list[dict[str, Any]]:
    try:
        response = client.context.relations(database=database, id=entity_id, type="knowledge", limit=limit)
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


def relation_entities(triplet: dict[str, Any]) -> tuple[str | None, str | None]:
    relation = triplet.get("relation") or triplet
    source_id = relation.get("source_entity_id") or relation.get("source") or triplet.get("source")
    target_id = relation.get("target_entity_id") or relation.get("target") or triplet.get("target")
    return relation_entity_id(source_id), relation_entity_id(target_id)


def relation_predicate(triplet: dict[str, Any]) -> str:
    relation = triplet.get("relation") or triplet
    return str(relation.get("canonical_predicate") or relation.get("raw_predicate") or relation.get("predicate") or "")


def query_param_entity() -> str:
    try:
        value = st.query_params.get("entity", "")
        return value[0] if isinstance(value, list) else str(value)
    except Exception:
        params = st.experimental_get_query_params()
        value = params.get("entity", [""])
        return value[0] if value else ""


def entity_link(entity_id: str, label: str) -> str:
    return f"?entity={quote(entity_id)}"


def main() -> None:
    st.set_page_config(page_title="Knowledge Explorer", layout="wide")
    st.title("Knowledge Explorer")

    database = st.sidebar.text_input("Database", DATABASE_NAME)
    refresh = st.sidebar.button("Refresh data")
    if refresh:
        cached_sources.clear()

    try:
        api_key = get_api_key()
        all_sources = cached_sources(database, api_key)
    except Exception as exc:
        st.error(f"Could not load HydraDB data: {exc}")
        return

    entities = [source for source in all_sources if metadata(source).get("type") == "Entity"]
    fact_states = [source for source in all_sources if metadata(source).get("type") == "FactState"]
    entities_by_id = {str(entity.get("id")): entity for entity in entities}

    default_entity = query_param_entity()
    query = st.text_input("Entity name or id", value=default_entity, placeholder="Sam Ratnaparkhi or entity-...")
    entity, match_score = resolve_entity(query, entities)

    if not entity:
        st.info("Enter an entity name or id to inspect its metadata, FactStates, and 1-hop relations.")
        return

    entity_id = str(entity.get("id"))
    meta = metadata(entity)
    extra = additional_metadata(entity)

    st.subheader(canonical_name(entity))
    st.caption(f"id: {entity_id} | match score: {match_score:.2f}")
    st.json(
        {
            "canonical_name": meta.get("canonical_name"),
            "aliases": aliases(entity),
            "entity_type": meta.get("entity_type"),
            "state": meta.get("state"),
            "additional_metadata": extra,
        },
        expanded=False,
    )

    entity_facts = [fact for fact in fact_states if str(metadata(fact).get("subject_id") or "") == entity_id]
    current_facts = [fact for fact in entity_facts if metadata(fact).get("state") == "current"]
    history_facts = sorted(
        [fact for fact in entity_facts if metadata(fact).get("state") == "superseded"],
        key=valid_from,
    )

    left, right = st.columns(2)
    with left:
        st.subheader("Current")
        if current_facts:
            st.dataframe(fact_rows(current_facts), use_container_width=True, hide_index=True)
        else:
            st.write("No current FactStates found.")
    with right:
        st.subheader("History")
        if history_facts:
            st.dataframe(fact_rows(history_facts), use_container_width=True, hide_index=True)
        else:
            st.write("No superseded FactStates found.")

    st.subheader("1-Hop Related Entities")
    client = HydraDB(token=api_key)
    related = []
    for triplet in relation_triplets(client, database, entity_id):
        source_id, target_id = relation_entities(triplet)
        neighbor_id = target_id if source_id == entity_id else source_id if target_id == entity_id else None
        if not neighbor_id:
            continue
        neighbor = entities_by_id.get(neighbor_id)
        label = canonical_name(neighbor) if neighbor else neighbor_id
        related.append((relation_predicate(triplet), neighbor_id, label))

    if related:
        seen = set()
        for predicate, neighbor_id, label in related:
            key = (predicate, neighbor_id)
            if key in seen:
                continue
            seen.add(key)
            st.markdown(f"- `{predicate or 'related_to'}` [{label}]({entity_link(neighbor_id, label)})")
    else:
        st.write("No 1-hop relations found.")


if __name__ == "__main__":
    main()
