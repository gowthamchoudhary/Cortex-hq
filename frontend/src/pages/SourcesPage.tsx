import { useCallback, useEffect, useRef, useState } from "react";
import {
  Cable,
  Database,
  Github,
  Loader2,
  CheckCircle2,
  Zap,
  Upload,
  ExternalLink,
  AlertCircle,
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
import {
  ingestSource,
  pollIngestJob,
  type IngestJobStatus,
} from "@/api/ingest";
import { getOAuthStatus, getOAuthStartUrl, disconnectOAuth } from "@/api/oauth";
import { PageHeader, EmptyState, ErrorState, LoadingState } from "@/components/shared/states";
import { useAuth } from "@/auth/AuthContext";
import { formatNumber, timeAgo } from "@/lib/format";
import type { SourcesResponse } from "@/types/api";

type SourceType = "gmail-export" | "slack-export" | "github-repo" | "document-upload" | "gmail-live" | "slack-live" | "github-live";

export function SourcesPage() {
  const { selectedBrain } = useAuth();
  const collection = selectedBrain;
  const [data, setData] = useState<SourcesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Ingestion state
  const [ingesting, setIngesting] = useState(false);
  const [ingestType, setIngestType] = useState<SourceType | null>(null);
  const [jobProgress, setJobProgress] = useState<IngestJobStatus | null>(null);
  const [ingestResult, setIngestResult] = useState<{
    ok: boolean;
    message: string;
  } | null>(null);
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // GitHub input
  const [showGitHubInput, setShowGitHubInput] = useState(false);
  const [githubRepo, setGithubRepo] = useState("");

  // OAuth status
  const [gmailConnected, setGmailConnected] = useState(false);
  const [slackConnected, setSlackConnected] = useState(false);
  const [githubConnected, setGithubConnected] = useState(false);

  // OAuth feedback from redirect
  const [oauthFeedback, setOauthFeedback] = useState<string | null>(null);

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

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollRef.current) clearTimeout(pollRef.current);
    };
  }, []);

  // Check OAuth status on mount and after redirect
  useEffect(() => {
    void load();
    const params = new URLSearchParams(window.location.search);
    const success = params.get("oauth_success");
    const oauthErr = params.get("oauth_error");
    if (success) {
      setOauthFeedback(`${success} connected successfully`);
      window.history.replaceState({}, "", window.location.pathname);
      setTimeout(() => void load(), 500);
    } else if (oauthErr) {
      setOauthFeedback(`OAuth error: ${oauthErr}`);
      window.history.replaceState({}, "", window.location.pathname);
    }
    void checkOAuthStatus();
  }, [load, collection]);

  const checkOAuthStatus = async () => {
    try {
      const [gmail, slack, github] = await Promise.all([
        getOAuthStatus("gmail", collection),
        getOAuthStatus("slack", collection),
        getOAuthStatus("github", collection),
      ]);
      setGmailConnected(gmail.connected);
      setSlackConnected(slack.connected);
      setGithubConnected(github.connected);
    } catch {
      // OAuth status check failed silently — not critical
    }
  };

  const startLiveIngest = async (sourceType: "gmail-live" | "slack-live") => {
    setIngesting(true);
    setIngestType(sourceType);
    setIngestResult(null);
    setJobProgress(null);
    try {
      const response = await ingestSource({
        collection,
        sourceType,
        sourceRepo: "",
      });
      // Start polling for progress
      void pollJob(response.job_id);
    } catch (err) {
      setIngestResult({
        ok: false,
        message: err instanceof Error ? err.message : "Ingestion failed.",
      });
      setIngesting(false);
      setIngestType(null);
    }
  };

  const startGitHubIngest = async () => {
    if (!githubRepo.trim()) return;
    setIngesting(true);
    setIngestType("github-repo");
    setIngestResult(null);
    setJobProgress(null);
    setShowGitHubInput(false);
    try {
      const response = await ingestSource({
        collection,
        sourceType: "github-repo",
        sourceRepo: githubRepo.trim(),
      });
      setGithubRepo("");
      void pollJob(response.job_id);
    } catch (err) {
      setIngestResult({
        ok: false,
        message: err instanceof Error ? err.message : "Ingestion failed.",
      });
      setIngesting(false);
      setIngestType(null);
    }
  };

  const pollJob = async (jobId: string) => {
    try {
      const finalJob = await pollIngestJob(
        jobId,
        (job) => setJobProgress(job),
        2000
      );
      if (finalJob.status === "completed" && finalJob.result) {
        const r = finalJob.result;
        setIngestResult({
          ok: true,
          message: `Ingestion complete: ${r.docs_processed} docs, ${r.entities_found} entities, ${r.merges_made} merges.`,
        });
        await load();
      } else {
        setIngestResult({
          ok: false,
          message: finalJob.error || "Ingestion failed.",
        });
      }
    } catch (err) {
      setIngestResult({
        ok: false,
        message: err instanceof Error ? err.message : "Ingestion failed.",
      });
    } finally {
      setIngesting(false);
      setIngestType(null);
      setJobProgress(null);
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

      {/* OAuth feedback banner */}
      {oauthFeedback && (
        <div
          className={`flex items-center gap-3 rounded-2xl border p-4 ${
            oauthFeedback.includes("error")
              ? "border-[#EF4444]/20 bg-[#EF4444]/5"
              : "border-[#10B981]/20 bg-[#10B981]/5"
          }`}
        >
          <CheckCircle2
            className="h-5 w-5 shrink-0"
            style={{ color: oauthFeedback.includes("error") ? "#EF4444" : "#10B981" }}
          />
          <p className="text-[13px] text-[#171717]">{oauthFeedback}</p>
        </div>
      )}

      {/* Platform Connect Buttons */}
      <div className="grid gap-3 sm:grid-cols-3">
        <OAuthConnectButton
          label="Gmail"
          icon={SiGmail}
          iconColor="#EA4335"
          connected={gmailConnected}
          connecting={ingesting && ingestType === "gmail-live"}
          onConnect={() => {
            window.location.href = getOAuthStartUrl("gmail", collection);
          }}
          onDisconnect={() => {
            void disconnectOAuth("gmail", collection).then(() => {
              setGmailConnected(false);
            });
          }}
          onSync={() => void startLiveIngest("gmail-live")}
        />
        <OAuthConnectButton
          label="Slack"
          icon={SlackIcon}
          iconColor="#4A154B"
          connected={slackConnected}
          connecting={ingesting && ingestType === "slack-live"}
          onConnect={() => {
            window.location.href = getOAuthStartUrl("slack", collection);
          }}
          onDisconnect={() => {
            void disconnectOAuth("slack", collection).then(() => {
              setSlackConnected(false);
            });
          }}
          onSync={() => void startLiveIngest("slack-live")}
        />
        <OAuthConnectButton
          label="GitHub"
          icon={SiGithub}
          iconColor="#7C3AED"
          connected={githubConnected}
          connecting={ingesting && ingestType === "github-repo"}
          onConnect={() => {
            window.location.href = getOAuthStartUrl("github", collection);
          }}
          onDisconnect={() => {
            void disconnectOAuth("github", collection).then(() => {
              setGithubConnected(false);
            });
          }}
          onSync={() => {
            if (githubConnected) {
              setShowGitHubInput(!showGitHubInput);
            }
          }}
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
              if (e.key === "Enter") void startGitHubIngest();
            }}
            placeholder="Paste repository URL (e.g. facebook/react)"
            className="flex-1 rounded-lg border border-black/[0.08] bg-[#FAFAF9] px-3 py-2 text-[13px] text-[#171717] placeholder:text-[#9A9A9A] outline-none transition-all duration-200 focus:border-[#171717]/20 focus:ring-1 focus:ring-[#171717]/5"
            autoFocus
          />
          <button
            type="button"
            onClick={() => void startGitHubIngest()}
            disabled={!githubRepo.trim()}
            className="btn-orange"
          >
            Connect
          </button>
        </div>
      )}

      {/* File Upload */}
      <FileUploadZone
        disabled={ingesting}
        onFileSelected={async (file, sourceType) => {
          setIngesting(true);
          setIngestType(sourceType);
          setIngestResult(null);
          setJobProgress(null);
          try {
            const response = await ingestSource({
              collection,
              sourceType,
              file,
            });
            void pollJob(response.job_id);
          } catch (err) {
            setIngestResult({
              ok: false,
              message: err instanceof Error ? err.message : "Ingestion failed.",
            });
            setIngesting(false);
            setIngestType(null);
          }
        }}
      />

      {/* Live Ingestion Progress */}
      {ingesting && jobProgress && (
        <IngestionProgress job={jobProgress} sourceType={ingestType} />
      )}

      {/* Simple loading state when job hasn't started polling yet */}
      {ingesting && !jobProgress && (
        <div className="flex items-center gap-3 rounded-2xl p-4 btn-green !cursor-default">
          <Loader2 className="h-5 w-5 shrink-0 animate-spin" />
          <div>
            <p className="text-[14px] font-medium">
              {ingestType === "github-repo"
                ? "Fetching repository data…"
                : ingestType === "gmail-live"
                ? "Fetching Gmail messages…"
                : ingestType === "slack-live"
                ? "Fetching Slack messages…"
                : "Processing file…"}
            </p>
            <p className="text-[12px] opacity-80">
              Starting background ingestion…
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
          {ingestResult.ok ? (
            <CheckCircle2 className="h-5 w-5 shrink-0 text-[#10B981]" />
          ) : (
            <AlertCircle className="h-5 w-5 shrink-0 text-[#EF4444]" />
          )}
          <p className="text-[13px] text-[#171717]">{ingestResult.message}</p>
        </div>
      )}

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
/* Ingestion Progress — live job status display                               */
/* -------------------------------------------------------------------------- */

function IngestionProgress({
  job,
  sourceType,
}: {
  job: IngestJobStatus;
  sourceType: SourceType | null;
}) {
  const progress = job.progress;
  const isRunning = job.status === "running";
  const isFailed = job.status === "failed";

  const sourceLabel =
    sourceType === "github-repo"
      ? "Repository"
      : sourceType === "gmail-live"
      ? "Gmail"
      : sourceType === "slack-live"
      ? "Slack"
      : "Document";

  return (
    <div className="rounded-2xl bg-white border border-black/[0.065] shadow-[0_2px_12px_rgba(0,0,0,0.04)] overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-3 px-5 py-4 border-b border-black/[0.04]">
        {isFailed ? (
          <AlertCircle className="h-5 w-5 text-[#EF4444] shrink-0" />
        ) : isRunning ? (
          <Loader2 className="h-5 w-5 text-[#F59E0B] shrink-0 animate-spin" />
        ) : (
          <Loader2 className="h-5 w-5 text-[#6B6B6B] shrink-0" />
        )}
        <div className="min-w-0 flex-1">
          <p className="text-[14px] font-semibold text-[#171717]">
            {isFailed
              ? `${sourceLabel} ingestion failed`
              : `Processing ${sourceLabel.toLowerCase()} data…`}
          </p>
          <p className="text-[12px] text-[#6B6B6B] mt-0.5">
            {progress.message}
          </p>
        </div>
        <span
          className="text-[11px] font-medium px-2 py-0.5 rounded-lg"
          style={{
            background: isFailed
              ? "rgba(239,68,68,0.1)"
              : "rgba(245,158,11,0.1)",
            color: isFailed ? "#EF4444" : "#F59E0B",
          }}
        >
          {isFailed ? "Failed" : isRunning ? "Running" : "Starting…"}
        </span>
      </div>

      {/* Progress bar */}
      {isRunning && (
        <div className="px-5 py-3 border-b border-black/[0.04]">
          <div className="h-1.5 rounded-full bg-[#F5F5F4] overflow-hidden">
            <div
              className="h-full rounded-full bg-gradient-to-r from-[#F59E0B] to-[#F97316] transition-all duration-500"
              style={{
                width: progress.docs_total > 0
                  ? `${Math.round((progress.docs_processed / progress.docs_total) * 100)}%`
                  : "30%",
              }}
            />
          </div>
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-3 gap-px bg-black/[0.04]">
        <div className="bg-white px-5 py-3 text-center">
          <p className="text-[18px] font-bold text-[#171717]">
            {progress.docs_processed}
          </p>
          <p className="text-[11px] text-[#6B6B6B]">
            Docs{progress.docs_total > 0 ? ` / ${progress.docs_total}` : ""}
          </p>
        </div>
        <div className="bg-white px-5 py-3 text-center">
          <p className="text-[18px] font-bold text-[#171717]">
            {progress.entities_found}
          </p>
          <p className="text-[11px] text-[#6B6B6B]">Entities</p>
        </div>
        <div className="bg-white px-5 py-3 text-center">
          <p className="text-[18px] font-bold text-[#171717]">
            {progress.merges_made}
          </p>
          <p className="text-[11px] text-[#6B6B6B]">Merges</p>
        </div>
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* File Upload Zone — drag-and-drop or click to upload                        */
/* -------------------------------------------------------------------------- */

function FileUploadZone({
  disabled,
  onFileSelected,
}: {
  disabled: boolean;
  onFileSelected: (file: File, sourceType: "gmail-export" | "slack-export" | "document-upload") => void;
}) {
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = (file: File) => {
    if (disabled) return;
    const name = file.name.toLowerCase();
    let sourceType: "gmail-export" | "slack-export" | "document-upload" = "document-upload";
    if (name.endsWith(".zip")) {
      // Detect Gmail vs Slack zip by checking for common patterns
      // Gmail zips typically contain MBOX files, Slack exports have channel dirs
      sourceType = "gmail-export"; // default to gmail; user can clarify if wrong
    } else if (name.endsWith(".mbox")) {
      sourceType = "gmail-export";
    }
    onFileSelected(file, sourceType);
  };

  return (
    <div
      className={`relative flex items-center gap-4 rounded-2xl border-2 border-dashed p-6 transition-all duration-200 ${
        dragOver
          ? "border-[#F59E0B] bg-[#F59E0B]/5 shadow-[0_2px_12px_rgba(245,158,11,0.1)]"
          : disabled
          ? "border-black/[0.06] bg-black/[0.02] opacity-60"
          : "border-black/[0.08] bg-white hover:border-black/[0.15] hover:shadow-[0_2px_12px_rgba(0,0,0,0.04)]"
      }`}
      onDragOver={(e) => {
        e.preventDefault();
        if (!disabled) setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragOver(false);
        const file = e.dataTransfer.files[0];
        if (file) handleFile(file);
      }}
      onClick={() => !disabled && inputRef.current?.click()}
    >
      <input
        ref={inputRef}
        type="file"
        className="hidden"
        accept=".zip,.mbox,.json,.jsonl,.txt,.md,.csv,.pdf,.docx"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) handleFile(file);
          e.target.value = "";
        }}
      />
      <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-[#F5F3F0]">
        <Upload className="h-5 w-5 text-[#6B6B6B]" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-[14px] font-semibold text-[#171717]">
          {dragOver ? "Drop file here" : "Upload a file"}
        </p>
        <p className="text-[12px] text-[#6B6B6B] mt-0.5">
          Gmail .zip, Slack .zip, or any document (PDF, TXT, DOCX, CSV, JSON)
        </p>
      </div>
      {dragOver && (
        <div className="absolute inset-0 rounded-2xl border-2 border-[#F59E0B] pointer-events-none" />
      )}
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* OAuth Connect Button — one click to OAuth or sync if connected             */
/* -------------------------------------------------------------------------- */

function OAuthConnectButton({
  label,
  icon: Icon,
  iconColor,
  connected,
  connecting,
  onConnect,
  onDisconnect,
  onSync,
}: {
  label: string;
  icon: React.ComponentType<{ size?: string | number; color?: string }>;
  iconColor: string;
  connected: boolean;
  connecting: boolean;
  onConnect: () => void;
  onDisconnect: () => void;
  onSync: () => void;
}) {
  return (
    <div className="relative">
      {connected ? (
        <div className="space-y-2">
          <div className="flex items-center gap-3 rounded-2xl bg-white border border-[#10B981]/20 p-4 shadow-[0_2px_8px_rgba(16,185,129,0.06)]">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[#10B981]/10">
              <Icon size={24} color={iconColor} />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-[14px] font-semibold text-[#171717]">{label}</p>
              <p className="text-[11px] text-[#10B981] font-medium">Connected</p>
            </div>
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={onSync}
              disabled={connecting}
              className="btn-orange flex-1"
            >
              {connecting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Syncing…
                </>
              ) : (
                <>
                  <Zap className="h-4 w-4" />
                  Sync now
                </>
              )}
            </button>
            <button
              type="button"
              onClick={onDisconnect}
              className="text-[12px] text-[#6B6B6B] hover:text-[#EF4444] transition-colors px-3"
            >
              Disconnect
            </button>
          </div>
        </div>
      ) : (
        <button
          type="button"
          onClick={onConnect}
          disabled={connecting}
          className="w-full flex items-center gap-3 rounded-2xl p-4 text-left transition-all duration-200 btn-orange hover:brightness-105"
        >
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white/16">
            <Icon size={24} color={iconColor} />
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-[14px] font-semibold text-white">Connect {label}</p>
            <p className="text-[11px] text-white/70">OAuth — one click to link</p>
          </div>
          <ExternalLink className="h-4 w-4 text-white/60 shrink-0" />
        </button>
      )}
    </div>
  );
}
