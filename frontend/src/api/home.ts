import { api } from "@/lib/api";
import type { HomeResponse } from "@/types/api";

export async function fetchHome(collection?: string): Promise<HomeResponse> {
  const query = collection ? `?collection=${encodeURIComponent(collection)}` : "";
  return api.get<HomeResponse>(`/home${query}`);
}
