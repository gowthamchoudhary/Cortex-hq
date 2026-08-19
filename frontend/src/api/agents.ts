import { api } from "@/lib/api";
import type { AgentsResponse } from "@/types/api";

export async function fetchAgents(): Promise<AgentsResponse> {
  return api.get<AgentsResponse>("/agents");
}

export interface CreateAgentResponse {
  ok: boolean;
  agent_id: string;
  agent_name: string;
  collection: string;
  role_default: string;
}

export async function createAgent(params: {
  collection?: string;
  agentName: string;
  roleDefault?: string;
}): Promise<CreateAgentResponse> {
  return api.post<CreateAgentResponse>("/agents/create", {
    collection: params.collection,
    agent_name: params.agentName,
    role_default: params.roleDefault || "member",
  });
}

export interface DeployAgentResponse {
  ok: boolean;
  status: string;
  agent_id: string;
  platform: string;
  config: Record<string, unknown>;
}

export async function deployAgent(params: {
  agentId: string;
  platform: "slack" | "github" | "email";
  config: Record<string, unknown>;
}): Promise<DeployAgentResponse> {
  return api.post<DeployAgentResponse>(
    `/agents/${encodeURIComponent(params.agentId)}/deploy`,
    {
      platform: params.platform,
      config: params.config,
    }
  );
}
