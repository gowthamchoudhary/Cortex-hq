import { api } from "@/lib/api";

export interface IngestResponse {
  ok: boolean;
  docs_processed: number;
  entities_found: number;
  merges_made: number;
  conflicts_resolved: number;
}

export async function ingestSource(params: {
  collection?: string;
  sourceType: "gmail-export" | "slack-export" | "github-repo" | "document-upload";
  file?: File;
  sourceRepo?: string;
}): Promise<IngestResponse> {
  const { collection, sourceType, file, sourceRepo } = params;

  if (sourceType === "github-repo") {
    // GitHub repo: POST JSON with source_repo
    return api.post<IngestResponse>("/ingest", {
      source_type: sourceType,
      source_repo: sourceRepo,
      collection,
    });
  }

  // Gmail/Slack: multipart file upload
  const formData = new FormData();
  formData.append("source_type", sourceType);
  if (collection) formData.append("collection", collection);
  if (file) formData.append("file", file);

  const headers: Record<string, string> = {};
  // The api helper sets Authorization header; we need to send it manually
  // for multipart requests since the helper doesn't support FormData.
  const token = (await import("@/lib/api")).getAccessToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const response = await fetch("/api/ingest", {
    method: "POST",
    headers,
    body: formData,
  });

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const message = body?.error || `Ingestion failed (${response.status})`;
    throw new Error(message);
  }

  return response.json();
}
