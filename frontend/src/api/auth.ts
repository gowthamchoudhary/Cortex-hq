import { api } from "@/lib/api";
import type { HealthResponse, MeResponse } from "@/types/api";

export async function fetchMe(): Promise<MeResponse> {
  return api.get<MeResponse>("/me");
}

export async function fetchHealth(): Promise<HealthResponse> {
  return api.get<HealthResponse>("/health");
}
