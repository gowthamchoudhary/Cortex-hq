import { useCallback, useEffect, useRef, useState } from "react";
import {
  Cable,
  Database,
  FileUp,
  Github,
  Loader2,
  CheckCircle2,
  Info,
} from "lucide-react";
import { SiGmail, SiGithub } from "@icons-pack/react-simple-icons";

/* Slack isn't in @icons-pack — hand-crafted multi-color mark */
function SlackIcon({ size = 22 }: { size?: string | number }) {
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} fill="none">
      <path d="M5.042 15.165a2.528 2.528 0 0 1-2.52 2.523A2.528 2.528 0 0 1 0 15.165a2.527 2.527 0 0 1 2.522-2.52h2.52v2.52z" fill="#E01E5A"/>
      <path d="M6.313 15.165a2.527 2.527 0 0 1 2.521-2.52 2.527 2.527 0 0 1 2.521 2.52v6.313A2.528 2.528 0 0 1 8.834 24a2.528 2.528 0 0 1-2.521-2.522v-6.313z" fill="#36C5F0"/>
      <path d="M6.313 8.834a2.527 2.527 0 0 1-2.521-2.52A2.528 2.528 0 0 1 6.313 3.79a2.527 2.527 0 0 1 2.521 2.522v2.522H6.313z" fill="#2EB67D"/>
      <path d="M8.834 6.313a2.528 2.528 0 0 1 2.521-2.521 2.528 2.528 0 0 1 2.521 2.521V8.83a2.528 2.528 0 0 1-2.521 2.521 2.527 2.527 0 0 1-2.521-2.52V6.313z" fill="#ECB22E"/>
      <path d="M15.165 6.313a2.528 2.528 0 0 1 2.523-2.521A2.528 2.528 0 0 1 20.21 6.313a2.527 2.527 0 0 1-2.522 2.52h-2.523V6.313z" fill="#36C5F0"/>
      <path d="M17.688 8.834a2.528 2.528 0 0 1 2.523 2.521 2.527 2.527 0 0 1-2.523 2.521h-6.312A2.528 2.528 0 0 1 8.834 11.355a2.528 2.528 0 0 1 2.52-2.521h6.312z" fill="#2EB67D"/>
      <path d="M15.165 17.688a2.527 2.527 0 0 1 2.523 2.523A2.528 2.528 0 0 1 15.165 22.73a2.527 2.527 0 0 1-2.52-2.52v-2.522h2.52z" fill="#E01E5A"/>
      <path d="M12.643 17.688a2.528 2.528 0 0 1-2.521 2.523 2.527 2.527 0 0 1-2.521-2.523v-6.312A2.528 2.528 0 0 1 10.122 8.834a2.527 2.527 0 0 1 2.521 2.521v6.313z" fill="#ECB22E"/>
      <path d="M8.834 15.165a2.528 2.528 0 0 1-2.521 2.523A2.527 2.527 0 0 1 3.79 15.165a2.528 2.528 0 0 1 2.522-2.52h2.522v2.52z" fill="#36C5F0"/>
    </svg>
  );
}
import { fetchSources } from "@/api/sources";
import { ingestSource } from "@/api/ingest";
import { PageHeader, EmptyState, ErrorState, LoadingState } from "@/components/shared/states";
import { useAuth } from "@/auth/AuthContext";
import { formatNumber, timeAgo } from "@/lib/format";
import type { SourcesResponse } from "@/types/api";

type SourceType = "gmail-export" | "slack-export" | "github-repo" | "document-upload";

export function SourcesPage() {
  const { selectedBrain } = useAuth();
  const collection = selectedBrain;
  const [data, setData] = useState<SourcesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Ingestion state
  const [ingesting, setIngesting] = useState(false);
  const [ingestType, setIngestType] = useState<SourceType | null>(null);
  const [ingestResult, setIngestResult] = useState<{
    ok: boolean;
    message: string;
  } | null>(null);

  // GitHub input
  const [showGitHubInput, setShowGitHubInput] = useState(false);
  const [githubRepo, setGithubRepo] = useState("");

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

  const handleFileIngest = async (
    sourceType: "gmail-export" | "slack-export" | "document-upload",
    file: File
  ) => {
    setIngesting(true);
    setIngestType(sourceType);
    setIngestResult(null);
    try {
      const result = await ingestSource({ collection, sourceType, file });
      setIngestResult({
        ok: true,
        message: `Ingestion complete: ${result.docs_processed} docs, ${result.entities_found} entities, ${result.merges_made} merges.`,
      });
      await load();
    } catch (err) {
      setIngestResult({
        ok: false,
        message: err instanceof Error ? err.message : "Ingestion failed.",
      });
    } finally {
      setIngesting(false);
      setIngestType(null);
    }
  };

  const handleGitHubIngest = async () => {
    if (!githubRepo.trim()) return;
    setIngesting(true);
    setIngestType("github-repo");
    setIngestResult(null);
    setShowGitHubInput(false);
    try {
      const result = await ingestSource({
        collection,
        sourceType: "github-repo",
        sourceRepo: githubRepo.trim(),
      });
      setIngestResult({
        ok: true,
        message: `Ingestion complete: ${result.docs_processed} docs, ${result.entities_found} entities, ${result.merges_made} merges.`,
      });
      setGithubRepo("");
      await load();
    } catch (err) {
      setIngestResult({
        ok: false,
        message: err instanceof Error ? err.message : "Ingestion failed.",
      });
    } finally {
      setIngesting(false);
      setIngestType(null);
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
      />

      {/* Connect Platform Buttons */}
      <div className="grid gap-3 sm:grid-cols-3">
        <ConnectButton
          label="Gmail"
          icon={SiGmail}
          iconColor="#EA4335"
          instruction="Export from Google Takeout → Gmail → download .zip"
          loading={ingesting && ingestType === "gmail-export"}
          onFileSelect={(file) => void handleFileIngest("gmail-export", file)}
          accept=".zip,.mbox"
        />
        <ConnectButton
          label="Slack"
          icon={SlackIcon}
          iconColor="#4A154B"
          instruction="Export from Slack Settings → Import/Export Data → download workspace .zip"
          loading={ingesting && ingestType === "slack-export"}
          onFileSelect={(file) => void handleFileIngest("slack-export", file)}
          accept=".zip"
        />
        <ConnectButton
          label="GitHub"
          icon={SiGithub}
           iconColor="#7C3AED"
          instruction="Enter a public or private repository (owner/name)"
          loading={ingesting && ingestType === "github-repo"}
          onClick={() => setShowGitHubInput(!showGitHubInput)}
        />
      </div>

      {/* GitHub single input */}
      {showGitHubInput && !ingesting && (
        <div className="flex items-center gap-3 rounded-2xl bg-white border border-black/[0.065] p-4 shadow-[0_2px_8px_rgba(0,0,0,0.04)]">
          <Github className="h-5 w-5 shrink-0" style={{ color: "#181717" }} />
          <input
            type="text"
            value={githubRepo}
            onChange={(e) => setGithubRepo(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") void handleGitHubIngest();
            }}
            placeholder="Paste repository URL (e.g. facebook/react)"
            className="flex-1 rounded-lg border border-black/[0.08] bg-[#FAFAF9] px-3 py-2 text-[13px] text-[#171717] placeholder:text-[#9A9A9A] outline-none transition-all duration-200 focus:border-[#171717]/20 focus:ring-1 focus:ring-[#171717]/5"
            autoFocus
          />
          <button
            type="button"
            onClick={() => void handleGitHubIngest()}
            disabled={!githubRepo.trim()}
            className="btn-orange !h-9 !text-[12px] !px-4"
          >
            Connect
          </button>
        </div>
      )}

      {/* Ingestion Progress */}
      {ingesting && (
        <div className="flex items-center gap-3 rounded-2xl p-4 btn-green !cursor-default">
          <Loader2 className="h-5 w-5 shrink-0 animate-spin" />
          <div>
            <p className="text-[14px] font-medium">
              {ingestType === "github-repo"
                ? "Fetching repository data…"
                : "Processing file…"}
            </p>
            <p className="text-[12px] opacity-80">
              Extraction, graph building, entity resolution — this may take a few minutes.
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

      {/* Generic Upload Zone */}
      <GenericUploadZone
        loading={ingesting}
        onFileSelect={(file) => void handleFileIngest("document-upload", file)}
      />

      {/* Source Breakdown */}
      {!data || sourceTypes.length === 0 ? (
        <EmptyState
          title="No connected sources"
          message="Click a platform above or upload a document to start ingesting knowledge."
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
/* Connect Button — one click opens file picker or triggers action             */
/* -------------------------------------------------------------------------- */

function ConnectButton({
  label,
  icon: Icon,
  iconColor,
  instruction,
  loading,
  onFileSelect,
  onClick,
  accept,
}: {
  label: string;
  icon: React.ComponentType<{ size?: string | number; color?: string }>;
  iconColor: string;
  instruction: string;
  loading: boolean;
  onFileSelect?: (file: File) => void;
  onClick?: () => void;
  accept?: string;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [showTooltip, setShowTooltip] = useState(false);

  const handleClick = () => {
    if (loading) return;
    if (onFileSelect) {
      inputRef.current?.click();
    } else if (onClick) {
      onClick();
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file && onFileSelect) {
      onFileSelect(file);
    }
    e.target.value = "";
  };

  return (
    <div className="relative">
      <button
        type="button"
        onClick={handleClick}
        disabled={loading}
         className={`w-full flex items-center gap-3 rounded-2xl p-4 text-left transition-all duration-200 ${
          loading
            ? "btn-green !rounded-2xl !h-auto !p-4 !justify-start !text-[13px]"
             : "btn-orange !rounded-2xl !h-auto !p-4 !justify-start !text-[13px] hover:brightness-105"
        }`}
      >
        {loading ? (
          <Loader2 className="h-5 w-5 shrink-0 animate-spin" />
        ) : (
          <div
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl"
             style={{ background: "rgba(255,255,255,0.16)" }}
          >
            <Icon size={24} color={iconColor} />
          </div>
        )}
        <div className="min-w-0 flex-1">
           <p className="text-[14px] font-semibold text-white">
            {loading ? `Connecting…` : label}
          </p>
        </div>
        {!loading && (
          <button
            type="button"
            className="shrink-0 p-1 rounded-lg hover:bg-black/[0.04] transition-colors"
            onClick={(e) => {
              e.stopPropagation();
              setShowTooltip(!showTooltip);
            }}
            aria-label={`Instructions for ${label}`}
          >
             <Info className="h-4 w-4 text-white/80" />
          </button>
        )}
      </button>

      {/* Tooltip */}
      {showTooltip && !loading && (
        <div className="absolute left-0 right-0 top-full z-10 mt-2 rounded-xl border border-black/[0.065] bg-white p-3 shadow-[0_8px_24px_rgba(0,0,0,0.08)]">
          <p className="text-[12px] text-[#6B6B6B] leading-relaxed">{instruction}</p>
        </div>
      )}

      {/* Hidden file input */}
      {onFileSelect && (
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          onChange={handleFileChange}
          className="hidden"
        />
      )}
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Generic Upload Zone — PDF/TXT/DOCX/CSV/JSON drag-and-drop or click          */
/* -------------------------------------------------------------------------- */

function GenericUploadZone({
  loading,
  onFileSelect,
}: {
  loading: boolean;
  onFileSelect: (file: File) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file && !loading) onFileSelect(file);
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) onFileSelect(file);
    e.target.value = "";
  };

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        if (!loading) setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={handleDrop}
      onClick={() => !loading && inputRef.current?.click()}
      className={`flex items-center gap-4 rounded-2xl border-2 border-dashed p-6 cursor-pointer transition-all duration-200 ${
        dragOver
          ? "border-[#EB512F]/40 bg-[#EB512F]/5"
          : "border-black/[0.08] bg-white hover:border-black/[0.15] hover:shadow-[0_2px_12px_rgba(0,0,0,0.04)]"
      } ${loading ? "opacity-50 pointer-events-none" : ""}`}
    >
      <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-[#F5F3F0]">
        <FileUp className="h-5 w-5 text-[#6B6B6B]" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-[14px] font-semibold text-[#171717]">Upload any document</p>
        <p className="text-[12px] text-[#6B6B6B] mt-0.5">
          PDF, TXT, DOCX, CSV, or JSON — drop a file or click to browse
        </p>
      </div>
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,.txt,.docx,.csv,.json,.jsonl,.md"
        onChange={handleChange}
        className="hidden"
      />
    </div>
  );
}
