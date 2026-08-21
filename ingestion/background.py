"""Background ingestion job runner with file-based job storage.

Jobs are persisted to /tmp as JSON files so they survive across Gunicorn
workers (which don't share in-memory state).  The frontend polls
``GET /api/ingest/status/<job_id>`` for progress.
"""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any

JOBS_DIR = Path(__file__).resolve().parents[1] / ".cortex_jobs"


def _new_job_id() -> str:
    return f"job-{uuid.uuid4().hex[:12]}"


def _job_path(job_id: str) -> Path:
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    return JOBS_DIR / f"{job_id}.json"


def _write_job(job: dict[str, Any]) -> None:
    path = _job_path(job["job_id"])
    path.write_text(json.dumps(job, default=str), encoding="utf-8")


def _read_job(job_id: str) -> dict[str, Any] | None:
    path = _job_path(job_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def start_ingestion_job(
    collection: str,
    source_type: str,
    source_path_or_repo: str,
    role_default: str = "admin",
) -> str:
    """Start ingestion in a background thread and return a job_id."""
    job_id = _new_job_id()
    job: dict[str, Any] = {
        "job_id": job_id,
        "status": "queued",
        "collection": collection,
        "source_type": source_type,
        "started_at": time.time(),
        "progress": {
            "phase": "queued",
            "message": "Waiting to start…",
            "docs_processed": 0,
            "docs_total": 0,
            "entities_found": 0,
            "merges_made": 0,
        },
        "result": None,
        "error": None,
    }
    _write_job(job)

    thread = threading.Thread(
        target=_run_job,
        args=(job_id, collection, source_type, source_path_or_repo, role_default),
        daemon=True,
    )
    thread.start()
    return job_id


def get_job(job_id: str) -> dict[str, Any] | None:
    """Return the current state of an ingestion job."""
    return _read_job(job_id)


def _run_job(
    job_id: str,
    collection: str,
    source_type: str,
    source_path_or_repo: str,
    role_default: str,
) -> None:
    """Execute the full ingestion pipeline inside a background thread."""
    from ingestion.ingest_pipeline import run_full_ingestion

    _update(job_id, status="running", phase="fetching", message="Fetching source data…")

    try:
        result = run_full_ingestion(
            collection=collection,
            source_type=source_type,
            source_path_or_repo=source_path_or_repo,
            role_default=role_default,
        )
        _update(
            job_id,
            status="completed",
            phase="done",
            message="Ingestion complete.",
            result=result,
        )
    except Exception as exc:
        msg = str(exc)
        if "GROQ_API_KEY" in msg or "OPENAI_API_KEY" in msg:
            user_msg = (
                "Missing LLM API key. Add GROQ_API_KEYS (comma-separated, free at console.groq.com/keys) "
                "or GROQ_API_KEY to your Render environment variables."
            )
        else:
            user_msg = msg
        _update(
            job_id,
            status="failed",
            phase="error",
            message=user_msg,
            error=user_msg,
        )
    finally:
        # Clean up source file if it was a temp upload
        if source_path_or_repo and os.path.exists(source_path_or_repo):
            try:
                os.unlink(source_path_or_repo)
            except OSError:
                pass


def _update(job_id: str, **fields: Any) -> None:
    job = _read_job(job_id)
    if job is None:
        return
    for key, value in fields.items():
        if key == "progress" and isinstance(value, dict):
            job["progress"].update(value)
        else:
            job[key] = value
    _write_job(job)
