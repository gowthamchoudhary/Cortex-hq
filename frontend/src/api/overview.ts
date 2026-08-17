import { api } from "@/lib/api";
import type { OverviewResponse } from "@/types/api";

export async function fetchOverview(collection?: string): Promise<OverviewResponse> {
  const query = collection ? `?collection=${encodeURIComponent(collection)}` : "";
  return api.get<OverviewResponse>(`/overview${query}`);
}
