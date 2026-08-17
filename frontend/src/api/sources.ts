import { api } from "@/lib/api";
import type { SourcesResponse } from "@/types/api";

export async function fetchSources(collection?: string): Promise<SourcesResponse> {
  const query = collection ? `?collection=${encodeURIComponent(collection)}` : "";
  return api.get<SourcesResponse>(`/sources${query}`);
}
