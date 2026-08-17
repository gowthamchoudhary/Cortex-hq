"""Agent configuration and deployment store for Cortex agents.

Agents are lightweight configuration records: which HydraDB collection an
agent is tied to, and the default role applied to anyone using it. A second
``deployments`` table records which platforms (slack, github, email, whatsapp)
an agent is live on plus each platform's config (bot tokens, webhook secrets).
Records live in a local SQLite store (``deploy/agents.db``) so no live backend
is required to define or inspect an agent.
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
VALID_PLATFORMS = ("slack", "github", "email", "whatsapp")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS agents (
    agent_id     TEXT PRIMARY KEY,
    agent_name   TEXT NOT NULL,
    collection   TEXT NOT NULL,
    role_default TEXT NOT NULL,
    created_at   INTEGER NOT NULL
);
"""

_SCHEMA_DEPLOYMENTS = """
CREATE TABLE IF NOT EXISTS deployments (
    agent_id    TEXT NOT NULL,
    platform    TEXT NOT NULL,
    config_json TEXT NOT NULL,
    status      TEXT NOT NULL,
    deployed_at INTEGER NOT NULL,
    PRIMARY KEY (agent_id, platform)
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
    connection.execute(_SCHEMA_DEPLOYMENTS)
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


def list_agents() -> list[dict[str, Any]]:
    """Return every agent config, each with its platform deployments.

    Read-only; used by the admin Agents UI. Deployments come from
    ``get_agent_deployments`` so a single response carries both the agent
    record and its live/pending platforms.
    """
    connection = _connect()
    try:
        rows = connection.execute(
            "SELECT agent_id, agent_name, collection, role_default, created_at "
            "FROM agents ORDER BY created_at DESC",
        ).fetchall()
    finally:
        connection.close()

    agents: list[dict[str, Any]] = []
    for agent_id, agent_name, collection, role_default, created_at in rows:
        try:
            deployments = get_agent_deployments(agent_id)
        except KeyError:
            deployments = []
        agents.append(
            {
                "agent_id": agent_id,
                "agent_name": agent_name,
                "collection": collection,
                "role_default": role_default,
                "created_at": created_at,
                "deployments": deployments,
            }
        )
    return agents


def deploy_agent(
    agent_id: str,
    platform: str,
    platform_config: dict[str, Any],
    status: str = "pending",
) -> dict[str, Any]:
    """Record that ``agent_id`` is deployed to ``platform`` with its config.

    ``platform`` is one of ``slack``, ``github``, ``email``, ``whatsapp``.
    ``platform_config`` holds whatever the adapter needs at runtime (bot
    tokens, webhook secrets, channel/workspace ids) — stored as JSON, never
    printed.

    ``status`` starts as ``"pending"``; set it to ``"active"`` once the
    adapter's webhook has been confirmed reachable (e.g. after the platform's
    URL-verification handshake succeeds). Re-deploying the same agent+platform
    upserts the config.
    """
    normalized_platform = str(platform).strip().lower()
    if normalized_platform not in VALID_PLATFORMS:
        raise ValueError(
            f"Unsupported platform {platform!r}; choose one of {', '.join(VALID_PLATFORMS)}."
        )
    if not isinstance(platform_config, dict) or not platform_config:
        raise ValueError("platform_config must be a non-empty dict.")
    if str(status).strip().lower() not in ("pending", "active", "disabled"):
        raise ValueError("status must be one of 'pending', 'active', 'disabled'.")

    get_agent_chat_endpoint(agent_id)  # Raises KeyError for unknown agents.

    import json

    connection = _connect()
    try:
        connection.execute(
            "INSERT INTO deployments (agent_id, platform, config_json, status, deployed_at) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT (agent_id, platform) "
            "DO UPDATE SET config_json = excluded.config_json, "
            "                status = excluded.status, "
            "                deployed_at = excluded.deployed_at",
            (
                str(agent_id),
                normalized_platform,
                json.dumps(platform_config, sort_keys=True),
                str(status).strip().lower(),
                int(time.time()),
            ),
        )
        connection.commit()
    finally:
        connection.close()

    return {
        "status": str(status).strip().lower(),
        "agent_id": str(agent_id),
        "platform": normalized_platform,
        "config": dict(platform_config),
    }


def get_agent_deployments(agent_id: str) -> list[dict[str, Any]]:
    """Return every platform deployment recorded for ``agent_id``."""
    import json

    get_agent_chat_endpoint(agent_id)  # Raises KeyError for unknown agents.
    connection = _connect()
    try:
        rows = connection.execute(
            "SELECT platform, config_json, status, deployed_at FROM deployments "
            "WHERE agent_id = ? ORDER BY platform",
            (str(agent_id),),
        ).fetchall()
    finally:
        connection.close()

    return [
        {
            "platform": platform,
            "config": json.loads(config_json or "{}"),
            "status": status,
            "deployed_at": deployed_at,
        }
        for platform, config_json, status, deployed_at in rows
    ]


def deploy_to_slack(
    agent_id: str,
    slack_workspace_config: dict[str, Any],
) -> dict[str, Any]:
    """Deprecated alias for ``deploy_agent(agent_id, "slack", config)``."""
    return deploy_agent(agent_id, "slack", slack_workspace_config)
