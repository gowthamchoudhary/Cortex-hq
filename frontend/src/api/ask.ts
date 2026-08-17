import { api } from "@/lib/api";
import type { AskResponse } from "@/types/api";

export async function askQuestion(question: string, collection?: string): Promise<AskResponse> {
  return api.post<AskResponse>("/ask", { question, collection });
}
