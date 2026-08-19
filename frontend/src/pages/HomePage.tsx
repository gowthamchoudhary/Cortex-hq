import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  FileText,
  FolderGit2,
  MessageSquare,
  CheckCircle2,
} from "lucide-react";
import { fetchHome } from "@/api/home";
import { Greeting } from "@/components/home/Greeting";
import { SuggestionCard } from "@/components/home/SuggestionCard";
import { AskBar } from "@/components/home/AskBar";
import { LoadingState, ErrorState, EmptyState } from "@/components/shared/states";
import { useAuth } from "@/auth/AuthContext";
import { timeAgo, formatNumber } from "@/lib/format";
import type { HomeResponse } from "@/types/api";

export function HomePage() {
  const { user, selectedBrain } = useAuth();
  const [data, setData] = useState<HomeResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState<string | null>(null);

  const collection = selectedBrain;

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await fetchHome(collection));
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load your workspace."
      );
    } finally {
      setLoading(false);
    }
  }, [collection]);

  useEffect(() => {
    void load();
  }, [load]);

  const name =
    (user?.user_metadata?.full_name as string | undefined)?.trim() ||
    user?.email?.split("@")[0] ||
    "there";

  const onAsk = (prompt: string) => {
    setDraft(prompt);
  };

  return (
    <div className="space-y-8">
      <Greeting name={name} />

      {loading ? (
        <LoadingState rows={3} />
      ) : error ? (
        <ErrorState message={error} onRetry={() => void load()} />
      ) : !data || !data.available ? (
        <EmptyState
          title="Your workspace is ready"
          message={
            data?.reason === "not_configured"
              ? "HydraDB isn't configured on this instance yet. Once a knowledge source is connected, suggestions and activity will appear here."
              : "No knowledge has been connected yet. Once sources are ingested, suggestions and recent activity will appear here."
          }
        />
      ) : (
        <>
          {/* Suggestions */}
          {data.suggestions.length > 0 ? (
            <section>
              <h2 className="mb-4 text-[13px] font-semibold uppercase tracking-[0.06em] text-faint">
                Suggested for you
              </h2>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {data.suggestions.map((suggestion) => (
                  <SuggestionCard
                    key={suggestion.id}
                    suggestion={suggestion}
                    onAsk={onAsk}
                  />
                ))}
              </div>
            </section>
          ) : null}

          {/* Needs attention */}
          {data.needs_attention.length > 0 ? (
            <section className="attention-banner">
              <AlertTriangle />
              <div className="space-y-1">
                {data.needs_attention.map((item) => (
                  <p key={item.message} className="text-[13.5px] text-foreground">
                    <span className="font-semibold">
                      {formatNumber(item.count)}
                    </span>{" "}
                    {item.message}
                  </p>
                ))}
              </div>
            </section>
          ) : null}

          {/* Recent intelligence */}
          {data.recent.length > 0 ? (
            <section>
              <h2 className="mb-4 text-[13px] font-semibold uppercase tracking-[0.06em] text-faint">
                Recent intelligence
              </h2>
              <div className="dash-card overflow-hidden">
                {data.recent.slice(0, 8).map((item) => (
                  <div key={item.id} className="list-item">
                    <div className="list-item-icon">
                      {item.record_type === "entity" ? (
                        <FolderGit2 className="h-4 w-4" />
                      ) : item.record_type === "factstate" ? (
                        <MessageSquare className="h-4 w-4" />
                      ) : (
                        <FileText className="h-4 w-4" />
                      )}
                    </div>
                    <div className="list-item-content">
                      <p className="list-item-title" title={item.title}>
                        {item.title}
                      </p>
                      <div className="list-item-meta">
                        <span
                          className="inline-flex items-center rounded-md px-1.5 py-0.5 text-[10px] font-medium"
                          style={{
                            background: "hsl(var(--muted))",
                            color: "hsl(var(--muted-foreground))",
                          }}
                        >
                          {item.record_type}
                        </span>
                        <span className="capitalize">{item.source_type}</span>
                        <span className="ml-auto shrink-0">
                          {timeAgo(item.created_at)}
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          ) : (
            <EmptyState
              title="No recent activity yet"
              message="Ingested knowledge and agent activity will appear here as your organization's data flows in."
            />
          )}

          {/* Everything looks good */}
          {data.needs_attention.length === 0 && data.suggestions.length === 0 && (
            <div className="flex items-center gap-3 rounded-2xl border border-border p-4">
              <CheckCircle2
                className="h-5 w-5 shrink-0"
                style={{ color: "hsl(var(--success))" }}
              />
              <p className="text-[13.5px] text-muted-foreground">
                Everything looks good.
              </p>
            </div>
          )}
        </>
      )}

      {/* Ask */}
      <section>
        <h2 className="mb-4 text-[13px] font-semibold uppercase tracking-[0.06em] text-faint">
          Ask Cortex
        </h2>
        <AskBar
          key={draft ?? "ask"}
          collection={collection}
          initialQuestion={draft ?? undefined}
        />
      </section>
    </div>
  );
}
