"""Agent configuration store for deploying Cortex agents.

Agents are lightweight configuration records: which HydraDB collection an
agent is tied to, and the default role applied to anyone using it. Records
live in a local SQLite store (``deploy/agents.db``) so no live backend is
required to define or inspect an agent.
"""

from __future__ import annotations

import hashlib
import os
import re
import sqlite3
import time
from pathlib import Path
from typing import Any

DEPLOY_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = DEPLOY_DIR / "agents.db"
DATABASE_NAME = "hackhydra-track1"

VALID_ROLES = ("admin", "member", "guest")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS agents (
    agent_id     TEXT PRIMARY KEY,
    agent_name   TEXT NOT NULL,
    collection   TEXT NOT NULL,
    role_default TEXT NOT NULL,
    created_at   INTEGER NOT NULL
);
"""


def _db_path() -> Path:
    """Return the agent store path, honoring the CORTEX_AGENTS_DB override."""
    override = os.environ.get("CORTEX_AGENTS_DB")
    return Path(override) if override else DEFAULT_DB_PATH


def _connect() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path))
    connection.execute(_SCHEMA)
    connection.commit()
    return connection


def _slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return normalized[:64] or "agent"


def _agent_id(agent_name: str) -> str:
    payload = f"{_slug(agent_name)}|{time.time()}|{os.getpid()}"
    suffix = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:8]
    return f"agent-{_slug(agent_name)}-{suffix}"


def _validate_role(role: str) -> str:
    normalized_role = str(role).strip().lower()
    if normalized_role not in VALID_ROLES:
        raise ValueError(
            f"Unsupported role {role!r}; choose one of {', '.join(VALID_ROLES)}."
        )
    return normalized_role


def create_agent(
    collection: str,
    agent_name: str,
    role_default: str = "member",
) -> dict[str, Any]:
    """Store an agent config and return the created (or matching) record.

    ``collection`` is the HydraDB collection the agent answers from, and
    ``role_default`` is the access role applied to anyone using the agent.
    Creating an agent with a name that already exists updates that agent's
    config and returns the existing id instead of duplicating it.
    """
    if not str(collection).strip():
        raise ValueError("collection must not be empty.")
    if not str(agent_name).strip():
        raise ValueError("agent_name must not be empty.")
    normalized_role = _validate_role(role_default)

    connection = _connect()
    try:
        existing = connection.execute(
            "SELECT agent_id FROM agents WHERE agent_name = ?",
            (str(agent_name).strip(),),
        ).fetchone()
        if existing:
            agent_id = existing[0]
            connection.execute(
                "UPDATE agents SET collection = ?, role_default = ? WHERE agent_id = ?",
                (str(collection).strip(), normalized_role, agent_id),
            )
        else:
            agent_id = _agent_id(str(agent_name).strip())
            connection.execute(
                "INSERT INTO agents (agent_id, agent_name, collection, role_default, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    agent_id,
                    str(agent_name).strip(),
                    str(collection).strip(),
                    normalized_role,
                    int(time.time()),
                ),
            )
        connection.commit()
    finally:
        connection.close()

    return {
        "agent_id": agent_id,
        "agent_name": str(agent_name).strip(),
        "collection": str(collection).strip(),
        "role_default": normalized_role,
    }


def get_agent_chat_endpoint(agent_id: str) -> dict[str, Any]:
    """Return the parameters needed to call the answer pipeline for an agent.

    The returned dict maps directly onto ``reasoning.answer_question.answer_question``:
    pass ``database``, ``collection``, and ``role`` as keyword arguments.
    """
    connection = _connect()
    try:
        row = connection.execute(
            "SELECT agent_id, agent_name, collection, role_default FROM agents WHERE agent_id = ?",
            (str(agent_id),),
        ).fetchone()
    finally:
        connection.close()

    if row is None:
        raise KeyError(f"Unknown agent {agent_id!r}; create it with create_agent() first.")

    agent_id, agent_name, collection, role_default = row
    return {
        "agent_id": agent_id,
        "agent_name": agent_name,
        "pipeline": "reasoning.answer_question:answer_question",
        "database": DATABASE_NAME,
        "collection": collection,
        "role": role_default,
    }


def deploy_to_slack(
    agent_id: str,
    slack_workspace_config: dict[str, Any],
) -> dict[str, Any]:
    """Stub for deploying an agent to Slack.

    Validates that the agent exists and that a workspace config was supplied,
    then returns a ``pending`` status. Actual Slack bot wiring (app manifest,
    socket mode, event handlers) lands in a later step once this interface is
    finalised.
    """
    if not isinstance(slack_workspace_config, dict) or not slack_workspace_config:
        raise ValueError("slack_workspace_config must be a non-empty dict.")

    workspace = slack_workspace_config.get("workspace")
    if not workspace or not str(workspace).strip():
        raise ValueError(
            "slack_workspace_config must include a non-empty 'workspace' value."
        )

    get_agent_chat_endpoint(agent_id)  # Raises KeyError for unknown agents.

    return {
        "status": "pending",
        "agent_id": agent_id,
        "workspace": str(workspace).strip(),
        "note": "Slack deployment is stubbed; bot wiring is not yet implemented.",
    }
