import { api } from "@/lib/api";

export interface IngestJobResponse {
  ok: boolean;
  job_id: string;
  status: "queued" | "running" | "completed" | "failed";
}

export interface IngestJobProgress {
  phase: string;
  message: string;
  docs_processed: number;
  docs_total: number;
  entities_found: number;
  merges_made: number;
}

export interface IngestJobStatus {
  ok: boolean;
  job_id: string;
  status: "queued" | "running" | "completed" | "failed";
  collection: string;
  source_type: string;
  started_at: number;
  progress: IngestJobProgress;
  result: {
    docs_processed: number;
    entities_found: number;
    merges_made: number;
    conflicts_resolved: number;
  } | null;
  error: string | null;
}

export async function ingestSource(params: {
  collection?: string;
  sourceType:
    | "gmail-export"
    | "slack-export"
    | "github-repo"
    | "document-upload"
    | "gmail-live"
    | "slack-live";
  file?: File;
  sourceRepo?: string;
}): Promise<IngestJobResponse> {
  const { collection, sourceType, file, sourceRepo } = params;

  // Live OAuth sources: POST JSON (no file upload needed)
  if (sourceType === "gmail-live" || sourceType === "slack-live") {
    return api.post<IngestJobResponse>("/ingest", {
      source_type: sourceType,
      collection,
    });
  }

  if (sourceType === "github-repo") {
    return api.post<IngestJobResponse>("/ingest", {
      source_type: sourceType,
      source_repo: sourceRepo,
      collection,
    });
  }

  // Gmail/Slack file upload: multipart form
  const formData = new FormData();
  formData.append("source_type", sourceType);
  if (collection) formData.append("collection", collection);
  if (file) formData.append("file", file);

  const headers: Record<string, string> = {};
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

export async function getIngestJobStatus(
  jobId: string
): Promise<IngestJobStatus> {
  return api.get<IngestJobStatus>(`/ingest/status/${jobId}`);
}

/**
 * Poll an ingestion job until it completes or fails.
 * Returns the final job status.
 */
export async function pollIngestJob(
  jobId: string,
  onProgress?: (job: IngestJobStatus) => void,
  intervalMs: number = 2000,
  maxAttempts: number = 300 // 10 minutes max
): Promise<IngestJobStatus> {
  let attempts = 0;
  while (attempts < maxAttempts) {
    const job = await getIngestJobStatus(jobId);
    onProgress?.(job);
    if (job.status === "completed" || job.status === "failed") {
      return job;
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
    attempts++;
  }
  throw new Error("Ingestion timed out after 10 minutes");
}
