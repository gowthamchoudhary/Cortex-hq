# CORTEX

### The Organizational Context Layer

**Connect your scattered conversations, documents, code, issues, and decisions into a living context layer that your team and agents can use — anywhere, anytime.**

Cortex is not a chatbot. It is a knowledge platform that ingests your organization's communication and work artifacts, extracts the entities, facts, and relationships they contain, resolves those entities across sources, tracks how facts change over time, preserves evidence and history, and answers questions with role-aware access control.

```
        ┌────────────────────────────────────────────────────────────┐
        │                     CORTEX (Streamlit UI)                  │
        │   Landing / Explorer  ·  Admin dashboard  ·  Agents        │
        └───────────────┬───────────────────────────┬────────────────┘
                        │                           │
               ┌────────▼────────┐          ┌───────▼────────┐
               │  Supabase Auth  │          │  auth/*        │
               │ (Google · Email │          │  user→brain    │
               │  · Magic Link)  │          │  role mapping  │
               └────────┬────────┘          └───────┬────────┘
┌─────────────┐  ┌──────▼───────────────────────────▼─────────────┐
│  Connectors │  │                  HydraDB                        │
│  Gmail mbox │  │  Entity · FactState · RelationSet · Candidate   │
│  Slack exp. │──▶  Collections ("brains"), metadata schema,       │
│  GitHub API │  │  access levels, temporal validity, evidence     │
│  Bench JSON │  └──────▲───────────────────────────▲─────────────┘
└─────────────┘         │                           │
                 ┌──────┴───────┐           ┌───────┴──────────┐
                 │  Extraction  │           │  Reasoning       │
                 │  LLM-based   │           │  linking, hops,  │
                 │  (Groq/OpenAI│           │  confidence,     │
                 │   candidates)│           │  abstention      │
                 └──────────────┘           └──────────────────┘
```

---

## Table of Contents

- [What Cortex Does](#what-cortex-does)
- [Core Capabilities](#core-capabilities)
- [Tech Stack](#tech-stack)
- [Repository Structure](#repository-structure)
- [Getting Started](#getting-started)
- [The Pipeline, End to End](#the-pipeline-end-to-end)
- [Modules in Depth](#modules-in-depth)
- [Access Control & Roles](#access-control--roles)
- [Data Model](#data-model)
- [Authentication (Supabase)](#authentication-supabase)
- [Evaluation & Benchmarking](#evaluation--benchmarking)
- [CLI Reference](#cli-reference)
- [Troubleshooting](#troubleshooting)
- [Development](#development)
- [License](#license)

---

## What Cortex Does

Every company generates context: meeting transcripts, email threads, Slack conversations, code reviews, issues, documents, and decisions. That context is scattered across tools, duplicated, contradictory, and stale. Cortex turns it into **a single living graph**:

1. **Connect** — ingest conversations, documents, code, and issues from real exports and APIs (Gmail Takeout, Slack workspace exports, GitHub repositories, benchmark JSON).
2. **Extract** — use an LLM to pull candidate *entities*, *facts*, and *relations* out of each document, with confidence scores.
3. **Resolve** — deduplicate and merge the same person, project, or repo mentioned across sources; log candidate merges for review.
4. **Understand** — learn which source types are trustworthy, resolve conflicting facts by authority, corroboration, and recency, and mark facts `current` / `superseded` / `disputed` over time.
5. **Serve** — answer questions with entity linking, subgraph expansion, confidence scoring, abstention when evidence is thin, and **role-based access filtering** so admins, members, and guests see only what they're allowed to.

---

## Core Capabilities

| Capability | Where |
|---|---|
| Entity extraction from any source format | `extraction/` |
| Real Gmail (Google Takeout `.mbox`) ingestion, threaded | `ingestion/normalize.py` |
| Real Slack workspace export ingestion (users + mentions resolved) | `ingestion/normalize.py` |
| GitHub repo activity (PRs, issues, comments, commits, Discussions) | `ingestion/github_fetch.py` |
| End-to-end orchestration (ingest → extract → graph → resolve → truth → cascade) | `ingestion/ingest_pipeline.py` |
| HydraDB graph ingestion with upsert + ingestion status polling | `graph/ingest_to_hydradb.py` |
| Entity resolution (blocking, jaro-winkler, auto-merge, pending merges) | `resolution/entity_resolution.py` |
| Near-duplicate document detection (MinHash LSH) | `resolution/dedup.py` |
| Source-reliability learning (iterative truth discovery) | `temporal/truth_discovery.py` |
| Temporal conflict cascade (authority / corroboration / recency / LWW) | `temporal/conflict_cascade.py` |
| Role-filtered question answering with abstention | `reasoning/answer_question.py` |
| Organization "brain" provisioning | `onboarding/create_brain.py` |
| Admin dashboard aggregates | `dashboard/admin_stats.py` |
| Agent configuration & chat endpoints | `deploy/agent_manager.py` |
| Supabase sign-in (Google, email+password, magic link) + user→brain role mapping | `auth/` |
| Benchmarking (baseline, system eval, ablations, coverage filter, calibration) | `eval/` |
| CORTEX landing page / explorer UI | `explorer/knowledge_explorer.py` |

---

## Tech Stack

- **Python ≥ 3.12** managed with **uv**
- **HydraDB** (`hydradb-sdk`) — graph/vector knowledge store with metadata schemas, collections, temporal fields, and graph payloads
- **Streamlit** — frontend (landing page + explorer)
- **httpx** — LLM APIs (Groq / OpenAI) and GitHub REST/GraphQL
- **supabase-py** — session token validation for sign-in (Google, email+password, magic link)
- **NumPy** — abstention calibration fitting
- **SQLite** (stdlib) — lightweight local stores (agent configs, user→brain mapping)

---

## Repository Structure

```
.
├── auth/                         # Supabase authentication & access mapping
│   ├── supabase_client.py        #   lazy client init (SUPABASE_URL / SUPABASE_ANON_KEY)
│   ├── session.py                #   get_current_user(access_token) token validation
│   └── user_brains.py            #   SQLite user_id → (collection, role) mapping
├── dashboard/
│   └── admin_stats.py            # get_admin_dashboard_data(collection) aggregates
├── deploy/
│   └── agent_manager.py          # SQLite agent configs + chat endpoint params
├── eval/                         # Benchmarking
│   ├── baseline.py               #   BM25-style retrieval baseline (Fireflies + Gmail)
│   ├── run_system_eval.py        #   full graph-pipeline evaluation
│   ├── run_ablation.py           #   configuration ablations on a fixed sample
│   ├── filter_answerable_questions.py  # question↔ingested-doc coverage filter
│   └── results/                  #   baseline, batch extraction, real extraction outputs
├── explorer/
│   └── knowledge_explorer.py     # CORTEX landing page (Streamlit entry point)
├── extraction/
│   ├── extract.py                #   LLM extraction of entities/facts/relations
│   └── batch_extract.py          #   batched extraction with rate-limit backoff
├── graph/
│   └── ingest_to_hydradb.py      # build graph payloads + ingest + poll status
├── ingestion/
│   ├── normalize.py              #   raw→RawDocument adapters + export parsers
│   ├── github_fetch.py           #   GitHub REST + GraphQL activity connector
│   └── ingest_pipeline.py        #   run_full_ingestion orchestration
├── onboarding/
│   └── create_brain.py           # create_brain(org, user_id) + get_brain_status
├── reasoning/
│   ├── answer_question.py        #   role-filtered QA pipeline
│   └── calibrate_threshold.py    #   fit abstention threshold from judged results
├── resolution/
│   ├── entity_resolution.py      #   blocking + jaro-winkler merges
│   └── dedup.py                  #   MinHash LSH near-duplicate documents
├── schema/
│   ├── setup_database.py         #   create/fetch HydraDB database + metadata schema
│   └── create_collection.py      #   ensure a named collection ("brain") exists
├── temporal/
│   ├── truth_discovery.py        #   learned source reliability per source type
│   └── conflict_cascade.py       #   temporal conflict resolution
├── scripts/
│   └── build_check.js            #   hosting build sanity check (Node.js image)
├── Datasets/
│   ├── fireflies/                #   173 meeting transcripts
│   ├── gmail/                    #   5,000 email threads
│   └── questions/question.jsonl  #   500 benchmark QA questions
├── pyproject.toml                # uv project definition & dependencies
└── README.MD
```

---

## Getting Started

### Prerequisites

- **Python 3.12+** and **uv** (the project pins `requires-python = ">=3.12"`)
- A **HydraDB** account (the graph database) — `HYDRADB_API_KEY`
- At least one LLM key — **Groq** (`GROQ_API_KEY`, default `llama-3.1-8b-instant`) or **OpenAI** (`OPENAI_API_KEY`) — used for extraction and answer generation
- Optional: **Supabase** project (`SUPABASE_URL`, `SUPABASE_ANON_KEY`) for sign-in (Google, email+password, magic link), **GitHub** token for repo ingestion

### Install

```bash
uv sync                 # install locked dependencies into .venv
uv run python --version
```

The dependency set is small: `httpx`, `hydradb-sdk`, `streamlit`, `supabase`, `numpy`.

### Environment Variables

| Variable | Required | Used by | Purpose |
|---|---|---|---|
| `HYDRADB_API_KEY` | ✅ backend | schema, graph, resolution, temporal, reasoning, onboarding, dashboard | Authenticate to HydraDB |
| `HYDRADB_DATABASE` | optional | dashboard | Database name override (default `hackhydra-track1`) |
| `GROQ_API_KEY` | for Groq | extraction, eval, reasoning | LLM provider (auto-selected when set) |
| `GROQ_MODEL` | optional | extraction, eval, reasoning | Default `llama-3.1-8b-instant` |
| `OPENAI_API_KEY` | for OpenAI | extraction, eval, reasoning | LLM provider (auto-selected when set) |
| `OPENAI_MODEL` | optional | extraction, eval, reasoning | Default `gpt-4.1-mini` |
| `GITHUB_TOKEN` | github-repo | ingestion | GitHub API access for `fetch_repo_activity` |
| `SUPABASE_URL` | sign-in | auth | Supabase project URL |
| `SUPABASE_ANON_KEY` | sign-in | auth | Supabase anon/public key |
| `CORTEX_AGENTS_DB` | optional | deploy | Agent store path override |
| `CORTEX_USER_BRAINS_DB` | optional | auth | User→brain mapping path override |

Modules read keys from the environment directly or from a `.env` file at the project root (each module ships a `load_dotenv()` that only sets variables that are not already present).

### Run the App

```bash
uv run streamlit run explorer/knowledge_explorer.py \
  --server.address 0.0.0.0 --server.port ${PORT:-8501} --server.headless true
```

Behind a reverse proxy, also pass `--server.enableCORS false --server.enableXsrfProtection false`.

---

## The Pipeline, End to End

Everything is reachable as plain Python functions, so a UI or scheduler can compose the flow:

```python
from onboarding.create_brain import create_brain, get_brain_status
from ingestion.ingest_pipeline import run_full_ingestion
from reasoning.answer_question import answer_question
from dashboard.admin_stats import get_admin_dashboard_data

# 1. Provision a brain (collection) for an org, owned by the signed-in user
brain = create_brain("Acme Corp", user_id="user-123")      # -> {"collection_name": "acme-corp", "status": "ready"}

# 2. Ingest a real source into it (extraction, graph ingest, resolution, truth, cascade run automatically)
summary = run_full_ingestion(
    collection=brain["collection_name"],
    source_type="slack-export",        # "gmail-export" | "slack-export" | "github-repo" | benchmark types
    source_path_or_repo="exports/slack",   # for github-repo: "owner/repo" (needs GITHUB_TOKEN)
    role_default="admin",               # ingestion access default (admin → internal)
    access_level=None,                  # pass "restricted" explicitly when required
)
# -> {"docs_processed": n, "entities_found": n, "merges_made": n, "conflicts_resolved": n}

# 3. Ask a question — role is derived from the signed-in user, never passed by the UI
result = answer_question(
    question="Who owns the Q3 capacity plan?",
    database="hackhydra-track1",
    collection=brain["collection_name"],
    provider="auto", model=None, timeout_seconds=90, verbose=False,
    user_id="user-123",                 # role resolved from auth.user_brains
)
# -> {"answer": ..., "evidence": [...], "confidence": 0.87, "abstained": False}

# 4. Dashboard stats
stats = get_admin_dashboard_data(brain["collection_name"])
# -> {"total_documents": ..., "total_entities": ..., "total_facts": ..., ...}
```

### What `run_full_ingestion` does, step by step

1. **Load & normalize** the source via its connector (`parse_gmail_takeout`, `parse_slack_export`, `fetch_repo_activity`, or the benchmark adapters) into `RawDocument`s.
2. **Extract candidates** with the LLM (`extract_with_backoff` — retries on 429 with exponential backoff).
3. **Build graph records** (`build_graph_documents`) — deterministic `entity-*` / `fact-*` / `relations-*` ids, metadata schema, access level, temporal validity (`valid_from`/`valid_to`, `txn_from`/`txn_to`).
4. **Ingest to HydraDB** in batches (upsert + graph payload), polling `indexing_status` until completed.
5. **Resolve entities** (`run_resolution`) — block, compare, auto-merge confident duplicates, log pending merges as `CandidateMerge` records.
6. **Learn truth** (`run_truth_discovery`) — iterative reliability per source type; writes learned `authority_weight` to FactStates.
7. **Cascade conflicts** (`run_cascade`) — resolve each (subject, predicate) group by authority, corroboration, or recency; disputed groups are flagged.

---

## Modules in Depth

### `schema/` — Provisioning

- **`setup_database.py`** — creates or fetches the HydraDB database (`hackhydra-track1` by default) and registers the project's metadata schema (fields such as `type`, `subject_id`, `predicate`, `state`, `access_level`, `valid_from`, `txn_from`, …) so metadata filters work.
- **`create_collection.py`** — `ensure_collection(client, database, collection)` creates a collection if missing, seeding a `__collection_init__` marker record so empty-but-real collections are distinguishable.

### `ingestion/` — Sources

- **`normalize.py`** — the shared `RawDocument` shape (`source`, `source_id`, `author`, `timestamp`, `content`, `container_id`, `metadata`) plus:
  - *Benchmark adapters*: `normalize_slack`, `normalize_jira`, `normalize_github`, `normalize_gmail` for EnterpriseRAG-Bench JSON records.
  - *`parse_gmail_takeout(export_path)`* — real Google Takeout `.mbox` (stdlib `mailbox`); accepts a file or a Takeout directory; threads messages via `References`/`In-Reply-To` with a normalized-subject fallback; extracts plain/HTML bodies; emits `normalize_gmail`-shaped dicts.
  - *`parse_slack_export(export_dir)`* — real Slack exports (`channels.json`, `users.json`, per-channel per-day JSON); resolves `<@U…>` mentions to display names; preserves `thread_ts`/`subtype`/`reply_count`; emits `normalize_slack`-shaped dicts.
- **`github_fetch.py`** — `fetch_repo_activity(repo, token, limit=50)`:
  - REST: pull requests, issues (PRs filtered out), per-item issue + review comments, commits — all paginated.
  - GraphQL: Discussions with title, body, author, and **all replies** (paginated comments).
  - Rate limits: 429 / exhausted-rate-limit 403 → exponential backoff honoring `Retry-After` (same pattern as `batch_extract.py`).
  - Output is `normalize_github`-shaped; comments are folded into the body so extraction sees the full conversation.
- **`ingest_pipeline.py`** — `run_full_ingestion(collection, source_type, source_path_or_repo, role_default="member", access_level=None)`. Dispatch: `gmail-export` / `slack-export` / `github-repo` go through the real parsers; bare `gmail` / `slack` / `github` / `jira` still use the benchmark loaders.

### `extraction/` — LLM Graph Extraction

- **`extract.py`** — `extract_from_document(document, provider, …)` prompts the LLM for JSON with `candidate_entities`, `candidate_facts`, `candidate_relations`; sanitizes and tags each item with `source_doc_id`. Supports `--list-groq-models`.
- **`batch_extract.py`** — `run_batch(...)` walks source folders, runs extraction with **429 retry/backoff** (`extract_with_backoff`), writes `eval/results/batch_extraction_output.json` with `results`, `skipped`, and a summary.

### `graph/` — HydraDB Ingestion

- **`ingest_to_hydradb.py`** — `build_graph_documents(records, limit, default_access_level)` turns extraction results into `app_knowledge` + `graph_payload` records; `ingest_batch` upserts via `client.context.ingest`; `wait_for_ingestion` polls until every id reaches `completed`/`errored`. Ids are deterministic (`entity-<sha1>`, `fact-<sha1>`) so re-ingestion upserts cleanly. Also updates the metadata schema.

### `resolution/` — Entity Resolution

- **`entity_resolution.py`** — candidate entities are blocked by token overlap, email domain, and name overlap; pairs scored with **jaro-winkler**; scores above the auto-merge threshold merge immediately (union-find), scores in the pending band are recorded as `CandidateMerge` records; merges mark the survivor `resolved`, add `merged_into` on merged entities, repoint FactStates, and log evidence.
- **`dedup.py`** — MinHash LSH over document content to detect near-duplicate documents.

### `temporal/` — Facts Over Time

- **`truth_discovery.py`** — iteratively learns a reliability per **source type** from agreement patterns (group facts by normalized value; a fact's confidence rises with independent agreeing sources); writes learned weights back as `authority_weight`.
- **`conflict_cascade.py`** — groups FactStates by `(subject_id, predicate)`, buckets near-identical values, and resolves each group: **authority → corroboration → recency → last-write-wins**, marking winners `current`, losers `superseded`, and unresolved groups `disputed`. Supports `--disabled` (LWW only) and `--use-learned-authority`.

### `reasoning/` — Question Answering

`answer_question(question, database, collection, provider, model, timeout_seconds, verbose, …, role, user_id)`:

1. **Query understanding** — LLM extracts target entity mentions, intent (lookup/causal/temporal/completeness), and time scope.
2. **Entity linking** — mentions scored against entity aliases with jaro-winkler (≥ 0.75); no-anchor mentions trigger a fallback retrieval over the raw corpus.
3. **Subgraph expansion** — 2-hop neighborhood via relation triplets; FactStates filtered by the caller's **access level** (from role) and time scope.
4. **Confidence** — blend of subgraph density, evidence/doc counts, and link scores, minus disputed/fallback penalties.
5. **Abstention** — below the (calibrated) threshold or with no facts, returns a canned abstention with `abstained: true`.
6. **Answer generation** — LLM over a context packet with citations and evidence doc ids.

`verbose=True` returns `debug` with query understanding, links, confidence breakdown, and the full context packet. `--user-id` derives the role from `auth.user_brains` instead of the explicit `--role`.

### `onboarding/` — Brains

- **`create_brain(org_name, user_id=None)`** — slugifies the org name into a unique collection (`acme-corp`, `acme-corp-2`, …), ensures it exists, and — when `user_id` is provided (the authenticated Supabase user) — automatically registers the creator as `admin` via `auth.user_brains`.
- **`get_brain_status(collection_name)`** — collection readiness + document/entity/fact counts.

### `auth/` — Supabase Sign-In

Sign-in runs **client-side via Supabase's hosted auth**; the backend only validates the resulting token. Three methods are supported:

- **`supabase_client.py`** — lazy client from `SUPABASE_URL` + `SUPABASE_ANON_KEY` (import-safe; clear `RuntimeError` if unconfigured).
- **`session.py`** — `get_current_user(access_token)` → `{"user_id", "email"}` or `None` for missing/expired/invalid tokens (never raises for a bad token).
- **`user_brains.py`** — SQLite mapping (`auth/user_brains.db`, override `CORTEX_USER_BRAINS_DB`): `register_user_brain(user_id, collection, role="admin")`, `get_user_brains(user_id)`, `get_user_role_in_brain(user_id, collection)`.

### `deploy/` — Agents

- **`agent_manager.py`** — SQLite store (`deploy/agents.db`, override `CORTEX_AGENTS_DB`):
  - `create_agent(collection, agent_name, role_default="member")` — upsert by name; roles validated.
  - `get_agent_chat_endpoint(agent_id)` — returns `{database, collection, role, pipeline}` ready to call `reasoning.answer_question.answer_question`.
  - `deploy_agent(agent_id, platform, platform_config)` — records the platform(s) an agent is live on (slack/github/email/whatsapp) with their config in the SQLite store; `deploy_to_slack(...)` is kept as a deprecated alias.

### `dashboard/` — Admin Stats

- **`get_admin_dashboard_data(collection)`** — read-only `context.list` aggregation: `total_documents` (distinct `source_doc_id`s, matching how the graph ingestor tracks docs), `total_entities`, `total_facts`, `total_relations`, `pending_merges` (CandidateMerge with `state="pending"`), `disputed_facts` (FactStates with `state="disputed"`), `last_ingestion_timestamp` (max `created_at`/`txn_from`), and `source_type_breakdown` (per-`doc_source_type`).

### `explorer/` — Frontend

- **`knowledge_explorer.py`** — the CORTEX landing page: near-black canvas, concentrated electric-blue bottom glow, minimal nav, eyebrow, large sans-serif headline with an editorial serif-italic accent, pill CTA, and an integrations panel emerging from the bottom light. It is a single Streamlit entry point (`streamlit run explorer/knowledge_explorer.py`).

---

## Access Control & Roles

Roles are enforced in two places:

1. **Ingestion** (`ingest_pipeline.py`) — the access level stamped on every ingested record:
   - `guest` → `public`
   - `member` → `internal`
   - `admin` → `internal` *(company-wide default; `restricted` is only applied when explicitly requested via `access_level="restricted"`)*

2. **Querying** (`reasoning/answer_question.py`) — the caller's role maps to allowed access levels, applied client-side over FactStates during subgraph expansion:

| Role | Can see |
|---|---|
| `admin` | `public`, `internal`, `restricted` |
| `member` | `public`, `internal` |
| `guest` | `public` |

A UI never passes a role: the backend derives it from the signed-in Supabase user via `get_user_role_in_brain(user_id, collection)`. Users with no recorded grant fall back to the explicit `role` parameter (default `member`).

---

## Data Model

HydraDB collections hold knowledge records ("sources") with typed metadata:

| Record type | `metadata.type` | Key metadata |
|---|---|---|
| Entity | `Entity` | `entity_type`, `canonical_name`, `source_doc_id`, `confidence`, `state` (`candidate`/`resolved`), `access_level`; aliases in `additional_metadata` |
| FactState | `FactState` | `subject_id`, `predicate`, `state` (`candidate`/`current`/`superseded`/`disputed`), `valid_from`/`valid_to`, `txn_from`/`txn_to`, `authority_weight`, `corroboration_count`, `confidence`, `access_level`, `doc_source_type`; human value in `additional_metadata.value` |
| RelationSet | `Relation` | `source_doc_id`, `doc_source_type`, `confidence`, `state`, `access_level`; edges in the graph payload |
| CandidateMerge | — | `state` (`pending`/`merged`), scores, evidence |

Graph payloads attach entities and typed relations (`HAS_STATE`, domain predicates) so HydraDB can serve `context.relations` for subgraph traversal.

---

## Authentication (Supabase)

1. The client (web app) redirects to Supabase's hosted sign-in — **Google OAuth**, **email + password**, or **magic link** (passwordless email).
2. After login, the client holds a Supabase access token.
3. The backend calls `get_current_user(access_token)` → `{user_id, email}`.
4. `create_brain(org, user_id=…)` grants the user `admin` on their new brain; `answer_question(…, user_id=…)` derives the access role from the same mapping.

**Setup:** create a Supabase project → under Authentication → Providers, enable **Google** (configure the client ID/secret), **Email** (password login), and **Magic Link** → add `SUPABASE_URL` and `SUPABASE_ANON_KEY` to the environment.

All three providers share the exact same backend path: the client signs in however it likes, and `get_current_user()` validates whatever token Supabase issues. Enabling or disabling a provider is a Supabase dashboard toggle — no code changes needed.

---

## Evaluation & Benchmarking

The `Datasets/` corpus is the EnterpriseRAG-Bench style data: **173 Fireflies meeting transcripts**, **5,000 Gmail threads**, and **500 QA questions** (`Datasets/questions/question.jsonl`) with categories, gold answers, and `expected_doc_ids` (ground-truth source ids, `dsid_…`).

| Tool | What it does |
|---|---|
| `eval/baseline.py` | Naive retrieval baseline (token/IDF scoring) over Fireflies + Gmail + LLM answer/judge |
| `eval/run_system_eval.py` | Evaluates the full graph-reasoning pipeline against the benchmark |
| `eval/run_ablation.py` | Compares graph-reasoning configurations on one fixed question sample |
| `eval/filter_answerable_questions.py` | Filters `questions.jsonl` to those whose ground-truth docs were actually ingested (`--questions`, `--extraction-results`, `--output`); prints total / answerable / coverage % |
| `reasoning/calibrate_threshold.py` | Fits the abstention threshold from judged QA results (writes `reasoning/calibration.json`) |

> **Coverage note:** the benchmark's ground-truth doc ids span source types (Github/Jira/Slack/Confluence/…) that the shipped `Datasets/` folder does not fully contain, so `filter_answerable_questions.py` may report low coverage until the full corpus — or a real export — is ingested. That is expected behavior, not a bug.

Run an evaluation:

```bash
uv run python eval/baseline.py --limit 20 --provider groq
uv run python eval/run_system_eval.py --limit 20 --provider groq
uv run python eval/filter_answerable_questions.py
```

---

## CLI Reference

| Command | Purpose |
|---|---|
| `uv run streamlit run explorer/knowledge_explorer.py` | Landing page / app UI |
| `uv run python schema/setup_database.py` | Create/fetch the HydraDB database + schema |
| `uv run python schema/create_collection.py --collection acme` | Ensure a collection exists |
| `uv run python ingestion/normalize.py sample.jsonl --source-type slack` | Inspect normalized records |
| `uv run python extraction/batch_extract.py --sources fireflies,gmail --limit 20` | Batch LLM extraction |
| `uv run python graph/ingest_to_hydradb.py eval/results/batch_extraction_output.json --collection acme --dry-run` | Ingest graph candidates |
| `uv run python resolution/entity_resolution.py --collection acme --limit 500` | Resolve entities |
| `uv run python resolution/dedup.py --source local --output resolution/results/dedup_marks.json` | Find near-duplicate docs |
| `uv run python temporal/truth_discovery.py --collection acme` | Learn source reliability |
| `uv run python temporal/conflict_cascade.py --collection acme --use-learned-authority` | Resolve temporal conflicts |
| `uv run python reasoning/answer_question.py "Who owns Q3?" --collection acme --verbose` | Ask with debug output |
| `uv run python reasoning/calibrate_threshold.py --questions Datasets/questions/question.jsonl --target-probability 0.6` | Fit abstention threshold |
| `uv run python eval/baseline.py --limit 20` | Run retrieval baseline |
| `uv run python eval/filter_answerable_questions.py` | Question↔doc coverage filter |

Programmatic entry points: `onboarding.create_brain.create_brain`, `ingestion.ingest_pipeline.run_full_ingestion`, `reasoning.answer_question.answer_question`, `dashboard.admin_stats.get_admin_dashboard_data`, `deploy.agent_manager.*`, `auth.session.get_current_user`, `auth.user_brains.*`.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `HYDRADB_API_KEY environment variable is required.` | Add the key to the environment / `.env` (or the Keys tab in the platform UI) |
| `Supabase is not configured: SUPABASE_URL and SUPABASE_ANON_KEY …` | Add both keys; they're only needed for token validation |
| `GITHUB_TOKEN environment variable is required` | Needed only for `source_type="github-repo"` |
| `Rate limited … retrying` | Expected — both extraction and GitHub fetching back off exponentially on 429 |
| Blank / unstyled Streamlit preview | Usually a server-side error; check the dev-server logs; run `python3 -m py_compile` on the entry file |
| mbox parser finds no threads | Takeout exports may store mail in multiple `.mbox` files — pass the `Mail/` directory, not a single file |
| Low eval coverage (0% answerable) | Ground-truth docs for the benchmark aren't in the shipped `Datasets/` — ingest the full corpus or a real export first |
| `Failed to resolve container IP` in preview | Platform-side sandbox restart; restart the preview session |

---

## Development

- **Checks:** `python3 -m py_compile <file>` or `uv run --frozen python -m compileall <dir>`; the project pins Python ≥ 3.12 via uv.
- **Conventions:** modules ship a docstring, `from __future__ import annotations`, `load_dotenv()`-style env reading, `argparse` CLIs where a script entry point makes sense, and a shared `to_plain_data()` helper for HydraDB pydantic responses.
- **Local stores** (`deploy/agents.db`, `auth/user_brains.db`) are SQLite and honor `CORTEX_AGENTS_DB` / `CORTEX_USER_BRAINS_DB` overrides — point them at a temp path in tests.
- **Verification style:** every connector was exercised against synthetic fixtures (generated mbox, generated Slack export, mocked GitHub responses) with the pipeline's downstream stages mocked, so new work should keep those call signatures stable.

---

## License

MIT — see `LICENSE`.
