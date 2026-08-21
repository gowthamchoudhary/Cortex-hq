"""Background ingestion job runner.

Moves the heavy ingestion pipeline out of the synchronous Flask request
handler so Render's Gunicorn workers don't get killed by timeouts or OOM
during long-running extraction/resolution passes.

Job lifecycle:
    1. ``start_ingestion_job()`` creates a job, spawns a daemon thread,
       and returns a ``job_id`` immediately.
    2. The background thread runs ``run_full_ingestion()`` and updates the
       job dict in ``_jobs`` with progress and result.
    3. The frontend polls ``GET /api/ingest/status/<job_id>`` to display
       live progress.
"""

from __future__ import annotations

import threading
import time
import uuid
from typing import Any

_jobs: dict[str, dict[str, Any]] = {}
_lock = threading.Lock()


def _new_job_id() -> str:
    return f"job-{uuid.uuid4().hex[:12]}"


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
    with _lock:
        _jobs[job_id] = job

    thread = threading.Thread(
        target=_run_job,
        args=(job_id, collection, source_type, source_path_or_repo, role_default),
        daemon=True,
    )
    thread.start()
    return job_id


def get_job(job_id: str) -> dict[str, Any] | None:
    """Return the current state of an ingestion job."""
    with _lock:
        return dict(_jobs.get(job_id)) if job_id in _jobs else None


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


def _update(job_id: str, **fields: Any) -> None:
    with _lock:
        if job_id not in _jobs:
            return
        job = _jobs[job_id]
        for key, value in fields.items():
            if key == "progress" and isinstance(value, dict):
                job["progress"].update(value)
            else:
                job[key] = value
