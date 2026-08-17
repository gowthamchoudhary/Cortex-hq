import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, FileText, FolderGit2, MessageSquare } from "lucide-react";
import { fetchHome } from "@/api/home";
import { Greeting } from "@/components/home/Greeting";
import { SuggestionCard } from "@/components/home/SuggestionCard";
import { AskBar } from "@/components/home/AskBar";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState, ErrorState, LoadingState } from "@/components/shared/states";
import { useAuth } from "@/auth/AuthContext";
import { timeAgo, formatNumber } from "@/lib/format";
import type { HomeResponse } from "@/types/api";

export function HomePage() {
  const { user, brains } = useAuth();
  const [data, setData] = useState<HomeResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState<string | null>(null);

  const collection = brains[0]?.collection_name;

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await fetchHome(collection));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load your workspace.");
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
    <div className="space-y-9">
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
          action={<Badge variant="outline">{collection || "no collection"}</Badge>}
        />
      ) : (
        <>
          {/* Suggestions from real activity */}
          {data.suggestions.length > 0 ? (
            <section>
              <h2 className="mb-3 text-[13px] font-semibold uppercase tracking-[0.06em] text-faint">
                Suggested for you
              </h2>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {data.suggestions.map((suggestion) => (
                  <SuggestionCard key={suggestion.id} suggestion={suggestion} onAsk={onAsk} />
                ))}
              </div>
            </section>
          ) : null}

          {/* Needs attention */}
          {data.needs_attention.length > 0 ? (
            <section className="flex items-start gap-3 rounded-2xl border border-warning/25 bg-warning/5 p-4">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning" />
              <div className="space-y-1">
                {data.needs_attention.map((item) => (
                  <p key={item.message} className="text-[13.5px] text-foreground">
                    <span className="font-semibold">{formatNumber(item.count)}</span> {item.message}
                  </p>
                ))}
              </div>
            </section>
          ) : null}

          {/* Recent intelligence */}
          {data.recent.length > 0 ? (
            <section>
              <h2 className="mb-3 text-[13px] font-semibold uppercase tracking-[0.06em] text-faint">
                Recent intelligence
              </h2>
              <div className="grid gap-3 lg:grid-cols-2">
                {data.recent.slice(0, 6).map((item) => (
                  <Card key={item.id} className="rounded-xl">
                    <CardContent className="flex items-start gap-3 p-4">
                      <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground">
                        {item.record_type === "entity" ? (
                          <FolderGit2 className="h-4 w-4" />
                        ) : item.record_type === "factstate" ? (
                          <MessageSquare className="h-4 w-4" />
                        ) : (
                          <FileText className="h-4 w-4" />
                        )}
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-[13.5px] font-medium text-foreground" title={item.title}>
                          {item.title}
                        </p>
                        <div className="mt-1.5 flex items-center gap-2 text-[12px] text-faint">
                          <Badge variant="outline" className="px-1.5 py-0 text-[10px]">
                            {item.record_type}
                          </Badge>
                          <span>{item.source_type}</span>
                          <span className="ml-auto shrink-0">{timeAgo(item.created_at)}</span>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </section>
          ) : null}
        </>
      )}

      {/* Ask */}
      <section>
        <h2 className="mb-3 text-[13px] font-semibold uppercase tracking-[0.06em] text-faint">
          Ask Cortex
        </h2>
        <AskBar key={draft ?? "ask"} collection={collection} initialQuestion={draft ?? undefined} />
      </section>
    </div>
  );
}
