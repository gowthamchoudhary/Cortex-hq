"""Cortex API server — a thin HTTP layer over the existing Python modules.

The React frontend talks only to this server. Every endpoint delegates to the
existing backend modules (``auth``, ``dashboard``, ``deploy``, ``identity``,
``reasoning``, ``onboarding``, ``schema``); no business logic lives here.

Design rules:
* The backend remains authoritative. This file only adapts module calls to
  JSON over HTTP and never invents data: when a dependency (HydraDB,
  Supabase, an LLM provider) is unreachable or unconfigured, endpoints
  return ``available: False`` with a machine-readable ``reason`` instead of
  fabricating numbers.
* Auth: every ``/api/*`` route except ``/health`` requires
  ``Authorization: Bearer <supabase access token>``; the token is validated
  by ``auth.session.get_current_user`` (the same validator the Streamlit UI
  used), and roles are resolved from ``auth.user_brains``.

Run:  ``.venv/bin/python api/server.py``  (binds 0.0.0.0:8000 by default)
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from flask import Flask, jsonify, request  # noqa: E402

from auth.session import get_current_user  # noqa: E402
from auth.user_brains import get_user_brains  # noqa: E402
from dashboard.admin_stats import get_admin_dashboard_data  # noqa: E402
from dashboard.people_access import get_people_access_data  # noqa: E402
from deploy.agent_manager import list_agents  # noqa: E402
from schema.create_collection import DATABASE_NAME, load_dotenv  # noqa: E402

load_dotenv()

DEFAULT_COLLECTION = os.environ.get("CORTEX_DEFAULT_COLLECTION", "default")
API_PORT = int(os.environ.get("CORTEX_API_PORT", "8000"))

app = Flask(__name__)


# ---------------------------------------------------------------------------
# CORS (dev: the Vite dev server proxies /api, so this mainly matters for
# direct browser access and future hosted deployments).
# ---------------------------------------------------------------------------


@app.after_request
def _cors_headers(response: Any) -> Any:
    response.headers.setdefault("Access-Control-Allow-Origin", "*")
    response.headers.setdefault("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
    response.headers.setdefault(
        "Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With"
    )
    response.headers.setdefault("Access-Control-Max-Age", "86400")
    return response


@app.route("/api/<path:path>", methods=["OPTIONS"])
@app.route("/<path:path>", methods=["OPTIONS"])
def _preflight(path: str) -> Any:
    return ("", 204)


# ---------------------------------------------------------------------------
# Small helpers shared by the routes.
# ---------------------------------------------------------------------------


def _bearer_token() -> str | None:
    header = request.headers.get("Authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return None


def _authenticate() -> tuple[dict[str, str] | None, Any]:
    """Validate the bearer token. Returns (user, None) or (None, response)."""
    token = _bearer_token()
    if not token:
        return None, (jsonify({"ok": False, "error": "missing_token"}), 401)
    user = get_current_user(token)
    if not user:
        return None, (jsonify({"ok": False, "error": "invalid_token"}), 401)
    return user, None


def _error_response(message: str, status: int = 400) -> Any:
    return (jsonify({"ok": False, "error": message}), status)


def _hydra_key_status() -> str:
    """'ok' | 'not_configured' | 'unreachable' — never raises."""
    api_key = os.environ.get("HYDRADB_API_KEY")
    if not api_key:
        return "not_configured"
    try:
        from hydra_db import HydraDB

        HydraDB(token=api_key)
        return "ok"
    except Exception:
        return "unreachable"


def _ts_key(value: Any) -> tuple[int, Any]:
    """Comparable key for Unix timestamps and ISO strings."""
    if value in (None, ""):
        return (-1, "")
    if isinstance(value, (int, float)):
        return (1, float(value))
    text = str(value).strip()
    try:
        return (1, float(text))
    except ValueError:
        pass
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return (1, parsed.timestamp())
    except ValueError:
        return (0, text)


def _record_meta(record: dict[str, Any]) -> dict[str, Any]:
    metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
    extra = (
        record.get("additional_metadata")
        if isinstance(record.get("additional_metadata"), dict)
        else {}
    )
    merged = dict(extra)
    merged.update(metadata)
    return merged


def _record_type(record: dict[str, Any]) -> str:
    meta = _record_meta(record)
    return str(
        meta.get("record_type")
        or meta.get("type")
        or record.get("record_type")
        or record.get("type")
        or record.get("kind")
        or ""
    ).strip().casefold()


def _record_value(record: dict[str, Any], key: str) -> Any:
    meta = _record_meta(record)
    return meta.get(key, record.get(key))


def _record_title(record: dict[str, Any]) -> str:
    meta = _record_meta(record)
    for key in ("title", "subject", "name", "summary", "text", "question"):
        value = meta.get(key) or record.get(key)
        if value and str(value).strip():
            return str(value).strip().replace("\n", " ")[:180]
    return ""


def _list_records(collection: str) -> list[dict[str, Any]]:
    """Every knowledge record in a collection (paginated)."""
    from hydra_db import HydraDB

    api_key = os.environ.get("HYDRADB_API_KEY")
    if not api_key:
        raise RuntimeError("HYDRADB_API_KEY environment variable is required.")
    client = HydraDB(token=api_key)
    records: list[dict[str, Any]] = []
    page = 1
    while True:
        response = client.context.list(
            database=DATABASE_NAME,
            collection=collection,
            type="knowledge",
            page=page,
            page_size=100,
        )
        data = response.data
        if hasattr(data, "model_dump"):
            data = data.model_dump()
        elif hasattr(data, "dict"):
            data = data.dict()
        if not isinstance(data, dict):
            raise TypeError("HydraDB context.list returned an unexpected shape.")
        records.extend(item for item in (data.get("sources") or []) if isinstance(item, dict))
        pagination = data.get("pagination") or {}
        if not pagination.get("has_next"):
            break
        page += 1
    return records


def _hydra_available(collection: str) -> tuple[bool, str]:
    """Probe whether HydraDB data for ``collection`` can be served."""
    if _hydra_key_status() != "ok":
        return False, _hydra_key_status()
    try:
        _list_records(collection)
        return True, "ok"
    except Exception as exc:  # noqa: BLE001
        return False, "unreachable" if "HYDRADB_API_KEY" not in str(exc) else "not_configured"


def _collection_for(user: dict[str, str], explicit: str | None) -> str | None:
    """Pick the collection to serve: explicit query param > user's first brain > default."""
    if explicit and str(explicit).strip():
        return str(explicit).strip()
    brains = get_user_brains(str(user["user_id"]))
    if brains:
        return str(brains[0]["collection_name"])
    return DEFAULT_COLLECTION


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/api/health")
def health() -> Any:
    return jsonify(
        {
            "ok": True,
            "service": "cortex-api",
            "hydradb": _hydra_key_status(),
            "supabase": bool(os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_ANON_KEY")),
            "reasoning_provider": bool(
                os.environ.get("GROQ_API_KEY") or os.environ.get("OPENAI_API_KEY")
            ),
        }
    )


@app.get("/api/me")
def me() -> Any:
    user, error = _authenticate()
    if error:
        return error
    user_id = str(user["user_id"])
    brains = get_user_brains(user_id)
    role = str(brains[0]["role"]) if brains else "guest"
    name = ""
    if user.get("email"):
        name = str(user["email"]).split("@")[0]
    return jsonify(
        {
            "ok": True,
            "user": {"id": user_id, "email": user.get("email", ""), "name": name},
            "role": role,
            "brains": brains,
            "app": {"name": "Cortex"},
        }
    )


@app.post("/api/brains")
def create_brain_endpoint() -> Any:
    """Create a new organization brain. The authenticated user becomes admin."""
    user, error = _authenticate()
    if error:
        return error
    body = request.get_json(silent=True) or {}
    org_name = str(body.get("org_name") or "").strip()
    if not org_name:
        return _error_response("org_name is required", 400)

    from onboarding.create_brain import create_brain

    try:
        result = create_brain(
            org_name=org_name,
            user_id=str(user["user_id"]),
        )
    except Exception as exc:  # noqa: BLE001
        return _error_response(f"Failed to create brain: {exc}", 500)

    return jsonify({"ok": True, **result})


@app.post("/api/invitations/<token>/accept")
def accept_invitation_endpoint(token: str) -> Any:
    """Accept an invitation token and register the user on the brain."""
    user, error = _authenticate()
    if error:
        return error

    from identity.invitations import accept_invitation

    try:
        result = accept_invitation(
            token=str(token).strip(),
            user_id=str(user["user_id"]),
        )
    except Exception as exc:  # noqa: BLE001
        return _error_response(f"Failed to accept invitation: {exc}", 500)

    status = result.get("status")
    if status == "failure":
        return _error_response(result.get("reason", "invitation_failed"), 400)
    if status == "verification_required":
        return jsonify({"ok": False, **result}), 400

    return jsonify({"ok": True, **result})


@app.get("/api/home")
def home() -> Any:
    user, error = _authenticate()
    if error:
        return error
    collection = _collection_for(user, request.args.get("collection"))
    available, reason = _hydra_available(collection)

    payload: dict[str, Any] = {
        "ok": True,
        "collection": collection,
        "available": available,
        "reason": reason,
        "counts": {"entities": 0, "facts": 0, "relations": 0, "documents": 0},
        "suggestions": [],
        "recent": [],
        "needs_attention": [],
    }
    if not available:
        return jsonify(payload)

    try:
        stats = get_admin_dashboard_data(collection)
    except Exception as exc:  # noqa: BLE001
        payload["available"] = False
        payload["reason"] = "unreachable" if "HYDRADB_API_KEY" not in str(exc) else "not_configured"
        return jsonify(payload)

    payload["counts"] = {
        "entities": int(stats.get("total_entities") or 0),
        "facts": int(stats.get("total_facts") or 0),
        "relations": int(stats.get("total_relations") or 0),
        "documents": int(stats.get("total_documents") or 0),
    }

    # --- Recent intelligence -------------------------------------------------
    try:
        records = _list_records(collection)
    except Exception:  # noqa: BLE001
        records = []
    recent: list[dict[str, Any]] = []
    for record in records:
        created = _record_value(record, "created_at") or _record_value(record, "txn_from")
        if created in (None, ""):
            continue
        recent.append(
            {
                "id": str(record.get("id") or ""),
                "title": _record_title(record) or f"{_record_type(record) or 'record'} record",
                "record_type": _record_type(record),
                "source_type": str(_record_value(record, "doc_source_type") or "knowledge"),
                "created_at": created,
            }
        )
    recent.sort(key=lambda item: _ts_key(item["created_at"]), reverse=True)
    payload["recent"] = recent[:12]

    # --- Needs attention (real, from the graph) ------------------------------
    attention: list[dict[str, Any]] = []
    pending_merges = int(stats.get("pending_merges") or 0)
    disputed = int(stats.get("disputed_facts") or 0)
    if pending_merges:
        attention.append(
            {"level": "warning", "count": pending_merges, "message": "entity merges awaiting review"}
        )
    if disputed:
        attention.append(
            {"level": "warning", "count": disputed, "message": "facts marked as disputed"}
        )

    # --- Suggestions (templated on real data only) ---------------------------
    suggestions: list[dict[str, Any]] = []
    try:
        people = get_people_access_data(collection)
        employee_count = len(people)
    except Exception:  # noqa: BLE001
        employee_count = 0
    try:
        agents = list_agents()
        agent_count = len(agents)
    except Exception:  # noqa: BLE001
        agent_count = 0

    source_types = stats.get("source_type_breakdown") or {}
    if source_types:
        top_source = max(source_types, key=lambda k: int(source_types.get(k) or 0))
        suggestions.append(
            {
                "id": "top-source",
                "prompt": f"What's in the latest {top_source} knowledge?",
                "source": f"{int(source_types.get(top_source) or 0)} documents from {top_source}",
            }
        )
    if employee_count:
        suggestions.append(
            {
                "id": "people",
                "prompt": "Who owns what across the organization?",
                "source": f"{employee_count} people in the directory",
            }
        )
    if agent_count:
        suggestions.append(
            {
                "id": "agents",
                "prompt": "What can the deployed agents answer?",
                "source": f"{agent_count} agents deployed",
            }
        )
    if pending_merges:
        suggestions.append(
            {
                "id": "merges",
                "prompt": "Which entities still need to be merged?",
                "source": f"{pending_merges} pending merges",
            }
        )
    if disputed:
        suggestions.append(
            {
                "id": "disputed",
                "prompt": "Which facts are still disputed?",
                "source": f"{disputed} disputed facts",
            }
        )
    for item in recent[:3]:
        title = item["title"]
        suggestions.append(
            {
                "id": f'recent-{item["id"]}',
                "prompt": f'What changed in "{title}"?',
                "source": f"{item['source_type']} · {item['record_type']}",
            }
        )
    payload["suggestions"] = suggestions[:6]
    payload["needs_attention"] = attention[:4]
    return jsonify(payload)


@app.get("/api/overview")
def overview() -> Any:
    user, error = _authenticate()
    if error:
        return error
    collection = _collection_for(user, request.args.get("collection"))
    available, reason = _hydra_available(collection)

    payload: dict[str, Any] = {
        "ok": True,
        "collection": collection,
        "available": available,
        "reason": reason,
        "stats": {
            "total_documents": 0,
            "total_entities": 0,
            "total_facts": 0,
            "total_relations": 0,
            "pending_merges": 0,
            "disputed_facts": 0,
            "last_ingestion_timestamp": None,
            "source_type_breakdown": {},
        },
        "people_count": 0,
        "agents_count": 0,
    }
    if not available:
        return jsonify(payload)

    try:
        payload["stats"] = get_admin_dashboard_data(collection)
    except Exception as exc:  # noqa: BLE001
        payload["available"] = False
        payload["reason"] = "unreachable" if "HYDRADB_API_KEY" not in str(exc) else "not_configured"
        return jsonify(payload)

    try:
        payload["people_count"] = len(get_people_access_data(collection))
    except Exception:  # noqa: BLE001
        payload["people_count"] = 0
    try:
        payload["agents_count"] = len(list_agents())
    except Exception:  # noqa: BLE001
        payload["agents_count"] = 0
    return jsonify(payload)


@app.get("/api/knowledge")
def knowledge() -> Any:
    user, error = _authenticate()
    if error:
        return error
    collection = _collection_for(user, request.args.get("collection"))
    query = (request.args.get("q") or "").strip().lower()
    record_filter = (request.args.get("type") or "").strip().lower()

    try:
        records = _list_records(collection)
    except Exception as exc:  # noqa: BLE001
        return _error_response(
            "unreachable" if "HYDRADB_API_KEY" not in str(exc) else "not_configured", 503
        )

    items: list[dict[str, Any]] = []
    for record in records:
        record_type = _record_type(record)
        if record_filter and record_type != record_filter:
            continue
        title = _record_title(record)
        if query and query not in title.lower():
            continue
        items.append(
            {
                "id": str(record.get("id") or ""),
                "title": title or f"{record_type or 'record'} record",
                "record_type": record_type,
                "source_type": str(_record_value(record, "doc_source_type") or "knowledge"),
                "access_level": str(_record_value(record, "access_level") or "public"),
                "confidence": _record_value(record, "confidence"),
                "created_at": _record_value(record, "created_at") or _record_value(record, "txn_from"),
            }
        )
    items.sort(key=lambda item: _ts_key(item.get("created_at")), reverse=True)
    return jsonify({"ok": True, "collection": collection, "total": len(items), "items": items})


@app.get("/api/sources")
def sources() -> Any:
    user, error = _authenticate()
    if error:
        return error
    collection = _collection_for(user, request.args.get("collection"))
    try:
        stats = get_admin_dashboard_data(collection)
    except Exception as exc:  # noqa: BLE001
        return _error_response(
            "unreachable" if "HYDRADB_API_KEY" not in str(exc) else "not_configured", 503
        )
    return jsonify(
        {
            "ok": True,
            "collection": collection,
            "total_documents": int(stats.get("total_documents") or 0),
            "source_type_breakdown": stats.get("source_type_breakdown") or {},
            "last_ingestion_timestamp": stats.get("last_ingestion_timestamp"),
        }
    )


@app.get("/api/agents")
def agents() -> Any:
    user, error = _authenticate()
    if error:
        return error
    try:
        items = list_agents()
    except Exception as exc:  # noqa: BLE001
        return _error_response(str(exc), 500)
    return jsonify({"ok": True, "items": items})


@app.get("/api/people")
def people() -> Any:
    user, error = _authenticate()
    if error:
        return error
    collection = _collection_for(user, request.args.get("collection"))
    try:
        items = get_people_access_data(collection)
    except Exception as exc:  # noqa: BLE001
        return _error_response(str(exc), 500)
    return jsonify({"ok": True, "collection": collection, "items": items})


@app.get("/api/activity")
def activity() -> Any:
    user, error = _authenticate()
    if error:
        return error
    collection = _collection_for(user, request.args.get("collection"))

    events: list[dict[str, Any]] = []
    try:
        records = _list_records(collection)
        for record in records:
            created = _record_value(record, "created_at") or _record_value(record, "txn_from")
            if created in (None, ""):
                continue
            record_type = _record_type(record)
            events.append(
                {
                    "id": f'ingest-{record.get("id")}',
                    "kind": "ingestion",
                    "title": f"Ingested {record_type or 'record'} · {_record_title(record) or record.get('id')}",
                    "created_at": created,
                }
            )
    except Exception:  # noqa: BLE001
        pass

    try:
        for agent in list_agents():
            for deployment in agent.get("deployments") or []:
                events.append(
                    {
                        "id": f'deploy-{agent.get("agent_id")}-{deployment.get("platform")}',
                        "kind": "deployment",
                        "title": (
                            f"{agent.get('agent_name')} deployed to {deployment.get('platform')} "
                            f"({deployment.get('status')})"
                        ),
                        "created_at": deployment.get("deployed_at"),
                    }
                )
    except Exception:  # noqa: BLE001
        pass

    events.sort(key=lambda item: _ts_key(item.get("created_at")), reverse=True)
    return jsonify({"ok": True, "items": events[:40]})


@app.post("/api/ask")
def ask() -> Any:
    user, error = _authenticate()
    if error:
        return error
    body = request.get_json(silent=True) or {}
    question = str(body.get("question") or "").strip()
    if not question:
        return _error_response("question is required", 400)
    collection = _collection_for(user, str(body.get("collection") or ""))

    from reasoning.answer_question import answer_question

    try:
        result = answer_question(
            question=question,
            database=DATABASE_NAME,
            collection=collection,
            provider=str(body.get("provider") or "auto"),
            model=body.get("model"),
            timeout_seconds=int(body.get("timeout_seconds") or 90),
            verbose=False,
            role=str(body.get("role") or "member"),
            user_id=str(user["user_id"]),
        )
    except Exception as exc:  # noqa: BLE001
        message = str(exc)
        if "HYDRADB_API_KEY" in message:
            return _error_response("HydraDB is not configured on this instance.", 503)
        if "api key" in message.lower() or "not configured" in message.lower():
            return _error_response("The reasoning provider is not configured.", 503)
        return _error_response(f"Answering failed: {message}", 500)

    return jsonify(
        {
            "ok": True,
            "question": question,
            "collection": collection,
            "answer": result.get("answer", ""),
            "confidence": result.get("confidence", 0.0),
            "evidence": result.get("evidence", []),
            "abstained": bool(result.get("abstained")),
        }
    )


@app.post("/api/ingest")
def ingest() -> Any:
    """Ingest a source into a collection. Supports file upload (Gmail/Slack) and GitHub repo."""
    user, error = _authenticate()
    if error:
        return error
    collection = _collection_for(user, request.args.get("collection"))

    # Check if this is a multipart file upload (Gmail/Slack)
    source_type = (request.form.get("source_type") or "").strip().lower()
    source_repo = (request.form.get("source_repo") or "").strip()

    if not source_type:
        body = request.get_json(silent=True) or {}
        source_type = str(body.get("source_type") or "").strip().lower()
        source_repo = str(body.get("source_repo") or "").strip()

    if source_type not in ("gmail-export", "slack-export", "github-repo", "document-upload"):
        return _error_response("source_type must be gmail-export, slack-export, github-repo, or document-upload", 400)

    import tempfile
    from ingestion.ingest_pipeline import run_full_ingestion

    source_path = None
    try:
        if source_type in ("gmail-export", "slack-export"):
            uploaded = request.files.get("file")
            if not uploaded or not uploaded.filename:
                return _error_response("file upload is required for Gmail/Slack ingestion", 400)
            suffix = ".zip" if uploaded.filename.endswith(".zip") else ".mbox"
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir="/tmp")
            uploaded.save(tmp.name)
            tmp.close()
            source_path = tmp.name
        elif source_type == "github-repo":
            if not source_repo:
                return _error_response("source_repo (owner/repo) is required for GitHub ingestion", 400)
            source_path = source_repo
        elif source_type == "document-upload":
            uploaded = request.files.get("file")
            if not uploaded or not uploaded.filename:
                return _error_response("file upload is required for document ingestion", 400)
            # Read file content as text and run through extraction pipeline
            file_content = uploaded.read()
            suffix = Path(uploaded.filename).suffix.lower() or ".txt"
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir="/tmp")
            tmp.write(file_content)
            tmp.close()
            source_path = tmp.name
            # For generic docs, use "gmail" as the adapter (treats as generic text source)
            source_type = "gmail-export"

        result = run_full_ingestion(
            collection=collection,
            source_type=source_type,
            source_path_or_repo=source_path,
            role_default="admin",
        )
    except Exception as exc:  # noqa: BLE001
        return _error_response(f"Ingestion failed: {exc}", 500)
    finally:
        if source_path:
            try:
                import os
                os.unlink(source_path)
            except OSError:
                pass

    return jsonify({"ok": True, **result})


@app.post("/api/agents/create")
def create_agent_endpoint() -> Any:
    """Create a new agent in a collection."""
    user, error = _authenticate()
    if error:
        return error
    body = request.get_json(silent=True) or {}
    agent_name = str(body.get("agent_name") or "").strip()
    if not agent_name:
        return _error_response("agent_name is required", 400)
    collection = _collection_for(user, str(body.get("collection") or ""))
    role_default = str(body.get("role_default") or "member").strip()

    from deploy.agent_manager import create_agent

    try:
        result = create_agent(collection=collection, agent_name=agent_name, role_default=role_default)
    except Exception as exc:  # noqa: BLE001
        return _error_response(f"Failed to create agent: {exc}", 500)

    return jsonify({"ok": True, **result})


@app.post("/api/agents/<agent_id>/deploy")
def deploy_agent_endpoint(agent_id: str) -> Any:
    """Deploy an agent to a platform (Slack, GitHub, Email)."""
    user, error = _authenticate()
    if error:
        return error
    body = request.get_json(silent=True) or {}
    platform = str(body.get("platform") or "").strip().lower()
    if platform not in ("slack", "github", "email"):
        return _error_response("platform must be slack, github, or email", 400)
    platform_config = body.get("config") or {}
    if not isinstance(platform_config, dict) or not platform_config:
        return _error_response("config must be a non-empty object", 400)

    from deploy.agent_manager import deploy_agent

    try:
        result = deploy_agent(
            agent_id=str(agent_id).strip(),
            platform=platform,
            platform_config=platform_config,
            status="pending",
        )
    except Exception as exc:  # noqa: BLE001
        return _error_response(f"Failed to deploy agent: {exc}", 500)

    return jsonify({"ok": True, **result})


@app.post("/api/employees")
def register_employee_endpoint() -> Any:
    """Register an employee in the directory."""
    user, error = _authenticate()
    if error:
        return error
    collection = _collection_for(user, request.args.get("collection"))
    body = request.get_json(silent=True) or {}
    name = str(body.get("name") or "").strip()
    work_email = str(body.get("work_email") or "").strip()
    employee_id = str(body.get("employee_id") or "").strip()
    cortex_role = str(body.get("cortex_role") or "member").strip()
    department = str(body.get("department") or "").strip() or None
    role_title = str(body.get("role_title") or "").strip() or None

    if not name or not work_email:
        return _error_response("name and work_email are required", 400)
    if not employee_id:
        # Auto-generate employee_id from email prefix
        employee_id = work_email.split("@")[0].replace(".", "-").replace("+", "-")

    from identity.employee_directory import register_employee

    try:
        result = register_employee(
            collection=collection,
            employee_id=employee_id,
            name=name,
            work_email=work_email,
            department=department,
            role_title=role_title,
            cortex_role=cortex_role,
        )
    except Exception as exc:  # noqa: BLE001
        return _error_response(f"Failed to register employee: {exc}", 500)

    return jsonify({"ok": True, "employee": result})


@app.post("/api/invitations")
def create_invitation_endpoint() -> Any:
    """Create an invitation for an employee."""
    user, error = _authenticate()
    if error:
        return error
    collection = _collection_for(user, request.args.get("collection"))
    body = request.get_json(silent=True) or {}
    employee_id = str(body.get("employee_id") or "").strip()

    if not employee_id:
        return _error_response("employee_id is required", 400)

    from identity.invitations import create_invitation

    try:
        result = create_invitation(collection=collection, employee_id=employee_id)
    except Exception as exc:  # noqa: BLE001
        return _error_response(f"Failed to create invitation: {exc}", 500)

    return jsonify({"ok": True, **result})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=API_PORT, debug=True)
