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

import base64
import json
import os
import sys
import urllib.parse
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
from oauth.tokens import get_bot_token_for_collection  # noqa: E402
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


def _encode_oauth_state(collection: str, return_to: str, **extra: str) -> str:
    """Encode dynamic OAuth context into a base64 ``state`` parameter."""
    payload = {"c": collection, "r": return_to, **extra}
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()


def _decode_oauth_state(state: str) -> dict[str, str]:
    """Decode the ``state`` parameter from an OAuth callback."""
    try:
        return json.loads(base64.urlsafe_b64decode(state))
    except Exception:  # noqa: BLE001
        return {}


def _clean_redirect_uri(provider: str) -> str:
    """Return the clean callback URL for a provider (no query params)."""
    backend_base = request.host_url.rstrip("/")
    return f"{backend_base}/api/oauth/{provider}/callback"


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
        reason = result.get("reason", "invitation_failed")
        user_friendly = {
            "invalid_or_expired": "This invitation link is invalid or has expired.",
            "already_used": "This invitation has already been accepted.",
            "employee_not_found": "Employee record not found. Please ask your admin to re-send the invitation.",
        }.get(reason, f"Invitation failed: {reason}")
        return jsonify({"ok": False, "error": reason, "message": user_friendly}), 400
    if status == "verification_required":
        return jsonify({
            "ok": False,
            "error": "verification_required",
            "message": "Your work email has not been verified yet. Please verify your email first.",
            **{k: v for k, v in result.items() if k != "status"},
        }), 400

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

    if source_type not in ("gmail-export", "slack-export", "github-repo", "document-upload", "gmail-live", "slack-live"):
        return _error_response("source_type must be gmail-export, slack-export, github-repo, document-upload, gmail-live, or slack-live", 400)

    import tempfile
    from ingestion.ingest_pipeline import run_full_ingestion

    source_path = None
    try:
        if source_type in ("gmail-live", "slack-live"):
            # Live OAuth: no file upload needed; the pipeline fetches via API.
            result = run_full_ingestion(
                collection=collection,
                source_type=source_type,
                source_path_or_repo="",
                role_default="admin",
            )
            return jsonify({"ok": True, **result})

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


@app.get("/api/oauth/slack/bot-status")
def slack_bot_status() -> Any:
    """Check if a Slack bot token exists for the current collection.

    Returns ``{ok, connected, needs_slack_install, bot_user_id}``.
    Used by the Agents page to decide whether the "Install to Slack" button
    or a "connected" badge should show.
    """
    user, error = _authenticate()
    if error:
        return error
    collection = _collection_for(user, request.args.get("collection"))

    from oauth.tokens import get_token
    bot = get_token(collection, "slack", "bot")
    connected = bot is not None and (
        bot.get("expires_at") is None or int(bot.get("expires_at", 0)) > __import__("time").time()
    )
    # Extract bot_user_id from scopes metadata if available.
    bot_user_id = ""
    if connected and bot:
        scopes_str = bot.get("scopes") or ""
        for part in scopes_str.split(","):
            if part.startswith("bot_user_id:"):
                bot_user_id = part.split(":", 1)[1]
                break
    return jsonify({
        "ok": True,
        "connected": connected,
        "needs_slack_install": not connected,
        "bot_user_id": bot_user_id,
        "collection": collection,
    })


@app.post("/api/agents/<agent_id>/deploy")
def deploy_agent_endpoint(agent_id: str) -> Any:
    """Deploy an agent to a platform (Slack, GitHub, Email).

    For Slack: checks that a bot token exists for the agent's collection.
    If no bot token is found, returns ``needs_slack_install`` with a
    redirect URL instead of silently failing.
    """
    user, error = _authenticate()
    if error:
        return error
    body = request.get_json(silent=True) or {}
    platform = str(body.get("platform") or "").strip().lower()
    if platform not in ("slack", "github", "email"):
        return _error_response("platform must be slack, github, or email", 400)
    platform_config = body.get("config") or {}
    if not isinstance(platform_config, dict):
        return _error_response("config must be an object", 400)
    # Allow empty config for Slack — the server looks up the bot token from OAuth store.
    # Require non-empty config for GitHub and Email (they need user-provided values).
    if platform != "slack" and not platform_config:
        return _error_response("config must be a non-empty object", 400)

    # --- Slack: verify bot token exists for this collection ---
    if platform == "slack":
        from deploy.agent_manager import get_agent_chat_endpoint
        try:
            endpoint = get_agent_chat_endpoint(agent_id.strip())
        except KeyError:
            return _error_response(f"Unknown agent {agent_id!r}", 404)
        agent_collection = endpoint["collection"]
        bot = get_bot_token_for_collection(agent_collection, "slack")
        if bot is None:
            # The install URL must point to the backend (where OAuth start lives).
            backend_base = request.host_url.rstrip("/")
            install_url = f"{backend_base}/api/oauth/slack/start?collection={agent_collection}&return_to=agents&scope=full"
            return jsonify({
                "ok": False,
                "error": "needs_slack_install",
                "message": "No Slack bot token found for this organization. Install the Slack app with bot permissions first.",
                "install_url": install_url,
            }), 400
        # Inject the bot token into the platform config so it's stored
        # with the deployment record for reference.
        platform_config["bot_token"] = bot["access_token"]
        platform_config["source"] = "oauth"

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


# ---------------------------------------------------------------------------
# OAuth routes — Gmail and Slack (no auth required; redirect to provider)
# ---------------------------------------------------------------------------


@app.get("/api/oauth/<provider>/start")
def oauth_start(provider: str) -> Any:
    """Redirect to Google/Slack OAuth consent screen.

    ``collection`` query param is required so the callback can store
    the token against the right brain.
    """
    collection = (request.args.get("collection") or "").strip()
    if not collection:
        return _error_response("collection query param is required", 400)
    return_to = (request.args.get("return_to") or "").strip()  # e.g. "agents" or "sources"

    # Clean redirect_uri — no query params. Dynamic context goes in the state param.
    redirect_uri = _clean_redirect_uri(provider)
    encoded_redirect_uri = urllib.parse.quote(redirect_uri, safe="")
    state = _encode_oauth_state(collection, return_to)

    if provider == "gmail":
        client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
        if not client_id:
            return _error_response("GOOGLE_OAUTH_CLIENT_ID is not configured", 503)
        scopes = "openid email https://mail.google.com/"
        auth_url = (
            f"https://accounts.google.com/o/oauth2/v2/auth?"
            f"client_id={client_id}&redirect_uri={encoded_redirect_uri}"
            f"&response_type=code&scope={scopes}&access_type=offline&prompt=consent"
            f"&state={state}"
        )
        from flask import redirect
        return redirect(auth_url)

    if provider == "github":
        client_id = os.environ.get("GITHUB_OAUTH_CLIENT_ID")
        if not client_id:
            return _error_response("GITHUB_OAUTH_CLIENT_ID is not configured", 503)
        scopes = "repo read:org"
        auth_url = (
            f"https://github.com/login/oauth/authorize?"
            f"client_id={client_id}&redirect_uri={encoded_redirect_uri}"
            f"&scope={scopes}&state={state}"
        )
        from flask import redirect
        return redirect(auth_url)

    if provider == "slack":
        client_id = os.environ.get("SLACK_OAUTH_CLIENT_ID")
        if not client_id:
            return _error_response("SLACK_OAUTH_CLIENT_ID is not configured", 503)
        # ``scope`` query param controls which scopes we request:
        #   - "ingest" (default): user-scoped tokens for message ingestion only
        #   - "full":  adds bot scopes (chat:write, app_mentions:read) for agent deployment
        scope_mode = (request.args.get("scope") or "ingest").strip().lower()
        user_scopes = "channels:history channels:read users:read"
        bot_scopes = "chat:write app_mentions:read channels:history channels:read users:read" if scope_mode == "full" else "channels:history channels:read users:read"
        # Pass scope_mode in state so callback knows which scope set was requested.
        state_with_scope = _encode_oauth_state(collection, return_to, scope=scope_mode)
        auth_url = (
            f"https://slack.com/oauth/v2/authorize?"
            f"client_id={client_id}&redirect_uri={encoded_redirect_uri}"
            f"&scope={bot_scopes}&user_scope={user_scopes}"
            f"&state={state_with_scope}"
        )
        from flask import redirect
        return redirect(auth_url)

    return _error_response(f"Unsupported OAuth provider: {provider}", 400)


@app.get("/api/oauth/<provider>/callback")
def oauth_callback(provider: str) -> Any:
    """Handle OAuth callback, exchange code for token, store it, redirect to app."""
    code = (request.args.get("code") or "").strip()
    error = request.args.get("error") or ""

    # Decode dynamic context from the state parameter (not from query params).
    state = (request.args.get("state") or "").strip()
    state_data = _decode_oauth_state(state) if state else {}
    collection = (state_data.get("c") or "").strip()
    return_to = (state_data.get("r") or "sources").strip() or "sources"

    # CORTEX_APP_BASE_URL is the frontend URL (Vercel) for post-redirect.
    backend_base = request.host_url.rstrip("/")
    frontend_base = os.environ.get("CORTEX_APP_BASE_URL", backend_base)

    # Derive the redirect target from return_to.
    target_page = "agents" if return_to == "agents" else "sources"

    if error:
        from flask import redirect
        return redirect(f"{frontend_base}/app/{target_page}?oauth_error={error}")

    if not code:
        from flask import redirect
        return redirect(f"{frontend_base}/app/{target_page}?oauth_error=missing_code")

    if provider == "gmail":
        return _handle_gmail_callback(code, collection, frontend_base, target_page)
    if provider == "slack":
        return _handle_slack_callback(code, collection, frontend_base, target_page)
    if provider == "github":
        return _handle_github_callback(code, collection, frontend_base, target_page)

    from flask import redirect
    return redirect(f"{frontend_base}/app/{target_page}?oauth_error=unsupported_provider")


def _handle_gmail_callback(code: str, collection: str, frontend_base: str, target_page: str = "sources") -> Any:
    """Exchange Gmail authorization code for tokens."""
    from flask import redirect

    client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "")
    client_secret = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        return redirect(f"{frontend_base}/app/{target_page}?oauth_error=missing_google_credentials")

    # Token exchange redirect_uri must match the clean URL sent during authorization.
    redirect_uri = _clean_redirect_uri("gmail")

    import httpx
    token_resp = httpx.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
        timeout=15,
    )
    token_resp.raise_for_status()
    token_data = token_resp.json()

    from oauth.tokens import store_token
    store_token(
        collection=collection,
        provider="gmail",
        access_token=token_data["access_token"],
        refresh_token=token_data.get("refresh_token"),
        expires_in=token_data.get("expires_in"),
        scopes=token_data.get("scope", ""),
    )

    return redirect(f"{frontend_base}/app/{target_page}?oauth_success=gmail")


def _handle_slack_callback(code: str, collection: str, frontend_base: str, target_page: str = "sources") -> Any:
    """Exchange Slack authorization code for tokens.

    Slack OAuth v2 returns:
    - ``access_token`` (top level): the bot token (xoxb-…)
    - ``authed_user.access_token``: the user token (xoxp-…)
    - ``team.id``: workspace/team id
    - ``bot_user_id``: the bot's Slack user id

    We store **both** tokens:
    - user token (token_type="user") for ingestion
    - bot token (token_type="bot") for agent message replies
    """
    from flask import redirect

    client_id = os.environ.get("SLACK_OAUTH_CLIENT_ID", "")
    client_secret = os.environ.get("SLACK_OAUTH_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        return redirect(f"{frontend_base}/app/{target_page}?oauth_error=missing_slack_credentials")

    # Token exchange redirect_uri must match the clean URL sent during authorization.
    redirect_uri = _clean_redirect_uri("slack")

    import httpx
    token_resp = httpx.post(
        "https://slack.com/api/oauth.v2.access",
        data={
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
        },
        timeout=15,
    )
    token_resp.raise_for_status()
    token_data = token_resp.json()

    if not token_data.get("ok"):
        return redirect(f"{frontend_base}/app/{target_page}?oauth_error={token_data.get('error', 'slack_error')}")

    # --- Extract tokens from the v2 response ---
    # Top-level access_token is the BOT token (xoxb-…)
    bot_access_token = token_data.get("access_token", "")
    bot_user_id = token_data.get("bot_user_id", "")
    team = token_data.get("team") or {}
    team_id = team.get("id", "")
    team_name = team.get("name", "")

    # authed_user sub-object holds the USER token (xoxp-…)
    authed_user = token_data.get("authed_user") or {}
    user_access_token = authed_user.get("access_token", "")
    user_scopes = authed_user.get("scope", "")

    # Bot scopes from the top-level scope field
    bot_scopes = token_data.get("scope", "")

    from oauth.tokens import store_token

    # Store user token for ingestion (always)
    if user_access_token:
        store_token(
            collection=collection,
            provider="slack",
            access_token=user_access_token,
            scopes=user_scopes,
            token_type="user",
        )

    # Store bot token for agent deployment (always when present)
    if bot_access_token:
        # Encode team_id into the scopes field so we can look up tokens by team later.
        bot_metadata = f"team_id:{team_id},bot_user_id:{bot_user_id},team_name:{team_name}"
        combined_scopes = f"{bot_scopes},{bot_metadata}" if bot_scopes else bot_metadata
        store_token(
            collection=collection,
            provider="slack",
            access_token=bot_access_token,
            scopes=combined_scopes,
            token_type="bot",
        )

    return redirect(f"{frontend_base}/app/{target_page}?oauth_success=slack")


def _handle_github_callback(code: str, collection: str, frontend_base: str, target_page: str = "sources") -> Any:
    """Exchange GitHub authorization code for an access token."""
    from flask import redirect

    client_id = os.environ.get("GITHUB_OAUTH_CLIENT_ID", "")
    client_secret = os.environ.get("GITHUB_OAUTH_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        return redirect(f"{frontend_base}/app/{target_page}?oauth_error=missing_github_credentials")

    import httpx
    token_resp = httpx.post(
        "https://github.com/login/oauth/access_token",
        json={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
        },
        headers={"Accept": "application/json"},
        timeout=15,
    )
    token_resp.raise_for_status()
    token_data = token_resp.json()

    if token_data.get("error"):
        return redirect(
            f"{frontend_base}/app/{target_page}?oauth_error={token_data['error_description'] or token_data['error']}"
        )

    access_token = token_data.get("access_token", "")
    if not access_token:
        return redirect(f"{frontend_base}/app/{target_page}?oauth_error=no_token")

    # Fetch the authenticated user's login to store as metadata.
    login = ""
    try:
        user_resp = httpx.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            },
            timeout=10,
        )
        user_resp.raise_for_status()
        login = user_resp.json().get("login") or ""
    except Exception:  # noqa: BLE001
        pass

    from oauth.tokens import store_token
    store_token(
        collection=collection,
        provider="github",
        access_token=access_token,
        scopes="repo read:org",
        token_type="user",
    )

    return redirect(f"{frontend_base}/app/{target_page}?oauth_success=github")


@app.get("/api/oauth/status/<provider>")
def oauth_status(provider: str) -> Any:
    """Check if an OAuth token exists and is valid for a provider."""
    user, error = _authenticate()
    if error:
        return error
    collection = _collection_for(user, request.args.get("collection"))

    from oauth.tokens import is_token_valid
    valid = is_token_valid(collection, provider)
    return jsonify({"ok": True, "connected": valid, "provider": provider})


@app.post("/api/oauth/<provider>/disconnect")
def oauth_disconnect(provider: str) -> Any:
    """Remove stored OAuth token for a provider."""
    user, error = _authenticate()
    if error:
        return error
    collection = _collection_for(user, request.args.get("collection"))

    from oauth.tokens import delete_token
    deleted = delete_token(collection, provider)
    return jsonify({"ok": True, "disconnected": deleted})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=API_PORT, debug=True)
