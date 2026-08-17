import { api } from "@/lib/api";
import type { ActivityResponse } from "@/types/api";

export async function fetchActivity(collection?: string): Promise<ActivityResponse> {
  const query = collection ? `?collection=${encodeURIComponent(collection)}` : "";
  return api.get<ActivityResponse>(`/activity${query}`);
}
