import { api } from "@/lib/api";
import type { KnowledgeResponse } from "@/types/api";

export async function fetchKnowledge(params?: {
  collection?: string;
  q?: string;
  type?: string;
}): Promise<KnowledgeResponse> {
  const query = new URLSearchParams();
  if (params?.collection) query.set("collection", params.collection);
  if (params?.q) query.set("q", params.q);
  if (params?.type) query.set("type", params.type);
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return api.get<KnowledgeResponse>(`/knowledge${suffix}`);
}
