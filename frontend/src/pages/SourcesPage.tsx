import { useCallback, useEffect, useState } from "react";
import {
  Cable,
  Database,
  Plus,
  Mail,
  MessageSquare,
  Github,
  Upload,
  Loader2,
  CheckCircle2,
  FileArchive,
} from "lucide-react";
import { fetchSources } from "@/api/sources";
import { ingestSource } from "@/api/ingest";
import { PageHeader, EmptyState, ErrorState, LoadingState } from "@/components/shared/states";
import { useAuth } from "@/auth/AuthContext";
import { formatNumber, timeAgo } from "@/lib/format";
import type { SourcesResponse } from "@/types/api";

type SourceType = "gmail-export" | "slack-export" | "github-repo";

const SOURCE_OPTIONS: {
  type: SourceType;
  label: string;
  icon: typeof Mail;
  description: string;
  instruction: string;
}[] = [
  {
    type: "gmail-export",
    label: "Gmail",
    icon: Mail,
    description: "Import emails from a Gmail Takeout export",
    instruction: "Go to Google Takeout → select Gmail → download the .zip file",
  },
  {
    type: "slack-export",
    label: "Slack",
    icon: MessageSquare,
    description: "Import messages from a Slack workspace export",
    instruction: "Go to Slack Settings → Import Data → download the workspace export .zip",
  },
  {
    type: "github-repo",
    label: "GitHub",
    icon: Github,
    description: "Fetch issues, PRs, and discussions from a GitHub repository",
    instruction: "Enter the repository as owner/name (e.g. facebook/react)",
  },
];

export function SourcesPage() {
  const { selectedBrain } = useAuth();
  const collection = selectedBrain;
  const [data, setData] = useState<SourcesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showConnect, setShowConnect] = useState(false);

  // Ingestion state
  const [ingesting, setIngesting] = useState(false);
  const [ingestProgress, setIngestProgress] = useState<string>("");
  const [ingestResult, setIngestResult] = useState<{
    ok: boolean;
    message: string;
  } | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await fetchSources(collection));
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load sources."
      );
    } finally {
      setLoading(false);
    }
  }, [collection]);

  useEffect(() => {
    void load();
  }, [load]);

  const handleIngest = async (
    sourceType: SourceType,
    file?: File,
    repo?: string
  ) => {
    setIngesting(true);
    setIngestResult(null);
    setIngestProgress("Starting ingestion…");

    try {
      const typeLabel =
        sourceType === "gmail-export"
          ? "Gmail"
          : sourceType === "slack-export"
            ? "Slack"
            : "GitHub";

      setIngestProgress(
        `Processing ${typeLabel} data — this may take several minutes…`
      );

      const result = await ingestSource({
        collection,
        sourceType,
        file,
        sourceRepo: repo,
      });

      setIngestResult({
        ok: true,
        message: `Ingestion complete: ${result.docs_processed} documents, ${result.entities_found} entities found, ${result.merges_made} merges, ${result.conflicts_resolved} conflicts resolved.`,
      });

      // Refresh source data
      await load();
    } catch (err) {
      setIngestResult({
        ok: false,
        message:
          err instanceof Error ? err.message : "Ingestion failed.",
      });
    } finally {
      setIngesting(false);
    }
  };

  if (loading) return <LoadingState rows={4} />;
  if (error) return <ErrorState message={error} onRetry={() => void load()} />;

  const sourceTypes = Object.entries(data?.source_type_breakdown || {});

  return (
    <div className="space-y-8">
      <PageHeader
        title="Sources"
        subtitle={`${formatNumber(data?.total_documents ?? 0)} documents ingested`}
        actions={
          <button
            type="button"
            onClick={() => setShowConnect(!showConnect)}
            className="inline-flex items-center gap-2 rounded-xl px-4 py-2 text-[13px] font-medium text-white transition-all duration-200"
            style={{
              background: "linear-gradient(180deg, #252525 0%, #171717 100%)",
              boxShadow:
                "0 1px 2px rgba(0,0,0,0.15), inset 0 1px 0 rgba(255,255,255,0.08)",
              border: "1px solid rgba(255,255,255,0.10)",
            }}
          >
            <Plus className="h-4 w-4" />
            Connect a source
          </button>
        }
      />

      {/* Connect Source Panel */}
      {showConnect && (
        <ConnectSourcePanel
          onIngest={handleIngest}
          ingesting={ingesting}
          onClose={() => {
            setShowConnect(false);
            setIngestResult(null);
          }}
        />
      )}

      {/* Ingestion Progress Banner */}
      {ingesting && (
        <div className="flex items-center gap-3 rounded-2xl border border-[#F59E0B]/20 bg-[#F59E0B]/5 p-4">
          <Loader2
            className="h-5 w-5 shrink-0 animate-spin"
            style={{ color: "#F59E0B" }}
          />
          <div>
            <p className="text-[14px] font-medium text-[#171717]">
              {ingestProgress}
            </p>
            <p className="text-[12px] text-[#6B6B6B]">
              Ingestion includes extraction, graph building, entity resolution,
              and truth discovery.
            </p>
          </div>
        </div>
      )}

      {/* Ingestion Result */}
      {ingestResult && (
        <div
          className={`flex items-center gap-3 rounded-2xl border p-4 ${
            ingestResult.ok
              ? "border-[#10B981]/20 bg-[#10B981]/5"
              : "border-[#EF4444]/20 bg-[#EF4444]/5"
          }`}
        >
          <CheckCircle2
            className="h-5 w-5 shrink-0"
            style={{ color: ingestResult.ok ? "#10B981" : "#EF4444" }}
          />
          <p className="text-[13px] text-[#171717]">{ingestResult.message}</p>
        </div>
      )}

      {/* Source Breakdown */}
      {!data || sourceTypes.length === 0 ? (
        <EmptyState
          title="No connected sources"
          message="Your organization hasn't connected any sources yet. Click 'Connect a source' above to start ingesting knowledge."
        />
      ) : (
        <div className="dash-card">
          <div className="dash-card-header">
            <div className="flex items-center gap-2">
              <Cable className="h-4 w-4 text-faint" />
              <p className="dash-card-title">Source types</p>
            </div>
            {data.last_ingestion_timestamp ? (
              <span
                className="inline-flex items-center rounded-lg px-2 py-0.5 text-[11px] font-medium"
                style={{
                  background: "hsl(var(--muted))",
                  color: "hsl(var(--muted-foreground))",
                }}
              >
                Last ingestion {timeAgo(data.last_ingestion_timestamp)}
              </span>
            ) : null}
          </div>
          <div className="dash-card-body space-y-4.5">
            {sourceTypes.map(([type, count]) => {
              const max = Math.max(...sourceTypes.map(([, c]) => c), 1);
              return (
                <div key={type}>
                  <div className="mb-2 flex items-center justify-between text-[13.5px]">
                    <span className="flex items-center gap-2 font-medium capitalize text-foreground">
                      <Database className="h-3.5 w-3.5 text-faint" />
                      {type}
                    </span>
                    <span className="text-muted-foreground">
                      {formatNumber(count)} documents
                    </span>
                  </div>
                  <div className="progress-track">
                    <div
                      className="progress-fill"
                      style={{
                        width: `${Math.round((count / max) * 100)}%`,
                      }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Connect Source Panel                                                        */
/* -------------------------------------------------------------------------- */

function ConnectSourcePanel({
  onIngest,
  ingesting,
  onClose,
}: {
  onIngest: (
    sourceType: SourceType,
    file?: File,
    repo?: string
  ) => Promise<void>;
  ingesting: boolean;
  onClose: () => void;
}) {
  const [selectedType, setSelectedType] = useState<SourceType | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [repo, setRepo] = useState("");

  const handleSubmit = async () => {
    if (!selectedType) return;
    if (selectedType === "github-repo") {
      if (!repo.trim()) return;
      await onIngest(selectedType, undefined, repo.trim());
    } else {
      if (!file) return;
      await onIngest(selectedType, file);
    }
  };

  return (
    <div className="rounded-2xl bg-white border border-black/[0.065] shadow-[0_4px_20px_rgba(0,0,0,0.035)] p-6">
      <div className="flex items-center justify-between mb-5">
        <h3 className="text-[16px] font-semibold text-[#171717]">
          Connect a source
        </h3>
        <button
          type="button"
          onClick={onClose}
          className="text-[13px] text-[#6B6B6B] hover:text-[#171717] transition-colors"
        >
          Close
        </button>
      </div>

      {/* Source Type Selector */}
      {!ingesting && (
        <div className="grid gap-3 sm:grid-cols-3 mb-5">
          {SOURCE_OPTIONS.map((option) => {
            const Icon = option.icon;
            const isSelected = selectedType === option.type;
            return (
              <button
                key={option.type}
                type="button"
                onClick={() => {
                  setSelectedType(option.type);
                  setFile(null);
                  setRepo("");
                }}
                className={`flex flex-col items-center gap-2.5 rounded-xl border p-4 text-left transition-all duration-200 ${
                  isSelected
                    ? "border-[#171717]/20 bg-[#171717]/[0.03] shadow-sm"
                    : "border-black/[0.065] hover:border-black/[0.12] hover:shadow-[0_2px_8px_rgba(0,0,0,0.04)]"
                }`}
              >
                <div
                  className={`flex h-10 w-10 items-center justify-center rounded-xl ${
                    isSelected ? "bg-[#171717] text-white" : "bg-black/[0.04] text-[#6B6B6B]"
                  }`}
                >
                  <Icon className="h-5 w-5" />
                </div>
                <div className="text-center">
                  <p className="text-[14px] font-medium text-[#171717]">
                    {option.label}
                  </p>
                  <p className="text-[12px] text-[#6B6B6B] mt-0.5">
                    {option.description}
                  </p>
                </div>
              </button>
            );
          })}
        </div>
      )}

      {/* Form for selected type */}
      {selectedType && !ingesting && (
        <div className="border-t border-black/[0.065] pt-5">
          {selectedType === "github-repo" ? (
            <GitHubForm repo={repo} setRepo={setRepo} />
          ) : (
            <FileUploadForm
              sourceType={selectedType}
              file={file}
              setFile={setFile}
            />
          )}

          <button
            type="button"
            onClick={() => void handleSubmit()}
            disabled={
              ingesting ||
              (selectedType === "github-repo" ? !repo.trim() : !file)
            }
            className="mt-5 w-full flex items-center justify-center gap-2 rounded-xl px-5 py-3 text-[14px] font-medium text-white transition-all duration-200 disabled:opacity-40"
            style={{
              background: "linear-gradient(180deg, #252525 0%, #171717 100%)",
              boxShadow:
                "0 1px 2px rgba(0,0,0,0.15), inset 0 1px 0 rgba(255,255,255,0.08)",
              border: "1px solid rgba(255,255,255,0.10)",
            }}
          >
            <Upload className="h-4 w-4" />
            Start ingestion
          </button>
        </div>
      )}
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* GitHub Form                                                                 */
/* -------------------------------------------------------------------------- */

function GitHubForm({
  repo,
  setRepo,
}: {
  repo: string;
  setRepo: (v: string) => void;
}) {
  return (
    <div className="space-y-4">
      <div>
        <label className="block mb-1 text-[13px] font-medium text-[#171717]">
          Repository
        </label>
        <input
          type="text"
          value={repo}
          onChange={(e) => setRepo(e.target.value)}
          placeholder="owner/repo (e.g. facebook/react)"
          className="w-full rounded-xl border border-black/[0.08] bg-[#FAFAF9] px-4 py-3 text-[14px] text-[#171717] placeholder:text-[#9A9A9A] outline-none transition-all duration-200 focus:border-[#171717]/20 focus:ring-2 focus:ring-[#171717]/5"
        />
      </div>
      <p className="text-[12px] text-[#6B6B6B]">
        The GITHUB_TOKEN environment variable must be configured on the backend
        for GitHub ingestion to work.
      </p>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* File Upload Form                                                            */
/* -------------------------------------------------------------------------- */

function FileUploadForm({
  sourceType,
  file,
  setFile,
}: {
  sourceType: "gmail-export" | "slack-export";
  file: File | null;
  setFile: (f: File | null) => void;
}) {
  const option = SOURCE_OPTIONS.find((o) => o.type === sourceType)!;

  return (
    <div className="space-y-4">
      <p className="text-[13px] text-[#6B6B6B]">{option.instruction}</p>

      <div
        className={`relative flex flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed p-6 transition-all duration-200 ${
          file
            ? "border-[#10B981]/40 bg-[#10B981]/[0.03]"
            : "border-black/[0.12] hover:border-black/[0.2] bg-[#FAFAF9]"
        }`}
      >
        <input
          type="file"
          accept=".zip,.mbox"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          className="absolute inset-0 cursor-pointer opacity-0"
        />
        {file ? (
          <>
            <FileArchive
              className="h-8 w-8"
              style={{ color: "#10B981" }}
            />
            <p className="text-[13px] font-medium text-[#171717]">
              {file.name}
            </p>
            <p className="text-[12px] text-[#6B6B6B]">
              {(file.size / 1024 / 1024).toFixed(1)} MB
            </p>
          </>
        ) : (
          <>
            <Upload className="h-8 w-8 text-[#9A9A9A]" />
            <p className="text-[13px] text-[#6B6B6B]">
              Click to upload or drag and drop
            </p>
            <p className="text-[12px] text-[#9A9A9A]">
              .zip or .mbox files accepted
            </p>
          </>
        )}
      </div>
    </div>
  );
}
