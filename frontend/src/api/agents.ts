import { api } from "@/lib/api";
import type { AgentsResponse } from "@/types/api";

export async function fetchAgents(): Promise<AgentsResponse> {
  return api.get<AgentsResponse>("/agents");
}
