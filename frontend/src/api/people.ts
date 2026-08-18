import { api } from "@/lib/api";
import type { PeopleResponse } from "@/types/api";

export async function fetchPeople(collection?: string): Promise<PeopleResponse> {
  const query = collection ? `?collection=${encodeURIComponent(collection)}` : "";
  return api.get<PeopleResponse>(`/people${query}`);
}
