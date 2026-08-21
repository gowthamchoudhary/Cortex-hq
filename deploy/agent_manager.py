"""Agent configuration and deployment store for Cortex agents.

Agents are lightweight configuration records: which HydraDB collection an
agent is tied to, and the default role applied to anyone using it. A second
``deployments`` table records which platforms (slack, github, email, whatsapp)
an agent is live on plus each platform's config (bot tokens, webhook secrets).

Records are stored in Supabase Postgres so they survive Render
free-tier deploys/restarts.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from typing import Any

from auth.supabase_db import get_db_client, TABLE_AGENTS, TABLE_DEPLOYMENTS

DATABASE_NAME = "hackhydra-track1"

VALID_ROLES = ("admin", "member", "guest")
VALID_PLATFORMS = ("slack", "github", "email", "whatsapp")


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
    """Store an agent config and return the created (or matching) record."""
    if not str(collection).strip():
        raise ValueError("collection must not be empty.")
    if not str(agent_name).strip():
        raise ValueError("agent_name must not be empty.")
    normalized_role = _validate_role(role_default)

    client = get_db_client()
    name = str(agent_name).strip()

    # Check if agent with this name already exists
    existing = (
        client.table(TABLE_AGENTS)
        .select("agent_id")
        .eq("agent_name", name)
        .limit(1)
        .execute()
    )

    if existing.data:
        agent_id = existing.data[0]["agent_id"]
        client.table(TABLE_AGENTS).update({
            "collection": str(collection).strip(),
            "role_default": normalized_role,
        }).eq("agent_id", agent_id).execute()
    else:
        agent_id = _agent_id(name)
        client.table(TABLE_AGENTS).insert({
            "agent_id": agent_id,
            "agent_name": name,
            "collection": str(collection).strip(),
            "role_default": normalized_role,
            "created_at": int(time.time()),
        }).execute()

    return {
        "agent_id": agent_id,
        "agent_name": name,
        "collection": str(collection).strip(),
        "role_default": normalized_role,
    }


def get_agent_chat_endpoint(agent_id: str) -> dict[str, Any]:
    """Return the parameters needed to call the answer pipeline for an agent."""
    client = get_db_client()
    result = (
        client.table(TABLE_AGENTS)
        .select("agent_id,agent_name,collection,role_default")
        .eq("agent_id", str(agent_id))
        .limit(1)
        .execute()
    )
    if not result.data:
        raise KeyError(f"Unknown agent {agent_id!r}; create it with create_agent() first.")

    row = result.data[0]
    return {
        "agent_id": row["agent_id"],
        "agent_name": row["agent_name"],
        "pipeline": "reasoning.answer_question:answer_question",
        "database": DATABASE_NAME,
        "collection": row["collection"],
        "role": row["role_default"],
    }


def list_agents() -> list[dict[str, Any]]:
    """Return every agent config, each with its platform deployments."""
    client = get_db_client()
    result = (
        client.table(TABLE_AGENTS)
        .select("agent_id,agent_name,collection,role_default,created_at")
        .order("created_at", desc=True)
        .execute()
    )

    agents: list[dict[str, Any]] = []
    for row in result.data:
        try:
            deployments = get_agent_deployments(row["agent_id"])
        except KeyError:
            deployments = []
        agents.append({
            "agent_id": row["agent_id"],
            "agent_name": row["agent_name"],
            "collection": row["collection"],
            "role_default": row["role_default"],
            "created_at": row["created_at"],
            "deployments": deployments,
        })
    return agents


def deploy_agent(
    agent_id: str,
    platform: str,
    platform_config: dict[str, Any],
    status: str = "pending",
) -> dict[str, Any]:
    """Record that ``agent_id`` is deployed to ``platform`` with its config."""
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

    client = get_db_client()
    client.table(TABLE_DEPLOYMENTS).upsert({
        "agent_id": str(agent_id),
        "platform": normalized_platform,
        "config_json": json.dumps(platform_config, sort_keys=True),
        "status": str(status).strip().lower(),
        "deployed_at": int(time.time()),
    }, on_conflict="agent_id,platform").execute()

    return {
        "status": str(status).strip().lower(),
        "agent_id": str(agent_id),
        "platform": normalized_platform,
        "config": dict(platform_config),
    }


def get_agent_deployments(agent_id: str) -> list[dict[str, Any]]:
    """Return every platform deployment recorded for ``agent_id``."""
    get_agent_chat_endpoint(agent_id)  # Raises KeyError for unknown agents.

    client = get_db_client()
    result = (
        client.table(TABLE_DEPLOYMENTS)
        .select("platform,config_json,status,deployed_at")
        .eq("agent_id", str(agent_id))
        .order("platform")
        .execute()
    )
    return [
        {
            "platform": row["platform"],
            "config": json.loads(row.get("config_json") or "{}"),
            "status": row["status"],
            "deployed_at": row["deployed_at"],
        }
        for row in result.data
    ]


def deploy_to_slack(
    agent_id: str,
    slack_workspace_config: dict[str, Any],
) -> dict[str, Any]:
    """Deprecated alias for ``deploy_agent(agent_id, "slack", config)``."""
    return deploy_agent(agent_id, "slack", slack_workspace_config)
