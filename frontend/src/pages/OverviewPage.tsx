import * as React from "react";
import { useCallback, useEffect, useState } from "react";
import { Bot, Cable, Network, Users } from "lucide-react";
import { fetchOverview } from "@/api/overview";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { PageHeader, EmptyState, ErrorState, LoadingState } from "@/components/shared/states";
import { useAuth } from "@/auth/AuthContext";
import { formatNumber, timeAgo } from "@/lib/format";
import type { OverviewResponse } from "@/types/api";

export function OverviewPage() {
  const { brains } = useAuth();
  const [data, setData] = useState<OverviewResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const collection = brains[0]?.collection_name;

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await fetchOverview(collection));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load the overview.");
    } finally {
      setLoading(false);
    }
  }, [collection]);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) return <LoadingState rows={4} />;
  if (error) return <ErrorState message={error} onRetry={() => void load()} />;
  if (!data || !data.available) {
    return (
      <div>
        <PageHeader title="Overview" subtitle="What's happening across your organization." />
        <EmptyState
          title="No operational data yet"
          message={
            data?.reason === "not_configured"
              ? "HydraDB isn't configured on this instance yet — connect it to see sources, knowledge, and activity."
              : "Connect a source to start tracking ingestion, knowledge growth, and activity here."
          }
        />
      </div>
    );
  }

  const stats = data.stats;
  const sourceTypes = Object.entries(stats.source_type_breakdown || {});

  return (
    <div className="space-y-8">
      <PageHeader title="Overview" subtitle="Here's what's happening across your organization." />

      {/* The small set of meaningful numbers */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard icon={Cable} label="Connected sources" value={formatNumber(stats.total_documents)} hint={`${sourceTypes.length} source types`} />
        <StatCard icon={Users} label="People" value={formatNumber(data.people_count)} hint="in the directory" />
        <StatCard icon={Bot} label="Agents" value={formatNumber(data.agents_count)} hint="deployed" />
        <StatCard icon={Network} label="Knowledge" value={formatNumber(stats.total_entities)} hint={`${formatNumber(stats.total_facts)} facts · ${formatNumber(stats.total_relations)} relations`} />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Needs attention */}
        <Card>
          <CardHeader>
            <CardTitle>Needs attention</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2.5">
            {(stats.pending_merges || stats.disputed_facts) ? (
              <>
                {stats.pending_merges > 0 ? (
                  <AttentionRow count={stats.pending_merges} message="entity merges awaiting review" />
                ) : null}
                {stats.disputed_facts > 0 ? (
                  <AttentionRow count={stats.disputed_facts} message="facts marked as disputed" />
                ) : null}
              </>
            ) : (
              <p className="py-2 text-sm text-muted-foreground">Nothing needs attention right now.</p>
            )}
          </CardContent>
        </Card>

        {/* Sources */}
        <Card>
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <CardTitle>Sources</CardTitle>
            {stats.last_ingestion_timestamp ? (
              <Badge variant="outline">{timeAgo(stats.last_ingestion_timestamp)}</Badge>
            ) : null}
          </CardHeader>
          <CardContent className="space-y-3">
            {sourceTypes.length > 0 ? (
              sourceTypes.map(([type, count]) => {
                const max = Math.max(...sourceTypes.map(([, c]) => c), 1);
                return (
                  <div key={type}>
                    <div className="mb-1 flex items-center justify-between text-[13px]">
                      <span className="font-medium text-foreground">{type}</span>
                      <span className="text-muted-foreground">{formatNumber(count)}</span>
                    </div>
                    <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                      <div
                        className="h-full rounded-full bg-accent/70"
                        style={{ width: `${Math.round((count / max) * 100)}%` }}
                      />
                    </div>
                  </div>
                );
              })
            ) : (
              <p className="py-2 text-sm text-muted-foreground">No source types recorded yet.</p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function StatCard({
  icon: Icon,
  label,
  value,
  hint,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
  hint: string;
}) {
  return (
    <Card>
      <CardContent className="p-5">
        <div className="flex items-center gap-2 text-[13px] font-medium text-muted-foreground">
          <Icon className="h-4 w-4 text-faint" />
          {label}
        </div>
        <p className="mt-3 text-[28px] font-semibold leading-none tracking-tight text-foreground">
          {value}
        </p>
        <p className="mt-2 text-[12px] text-faint">{hint}</p>
      </CardContent>
    </Card>
  );
}

function AttentionRow({ count, message }: { count: number; message: string }) {
  return (
    <div className="flex items-center justify-between rounded-lg border border-warning/25 bg-warning/5 px-3.5 py-2.5">
      <p className="text-[13px] text-foreground">
        <span className="font-semibold">{formatNumber(count)}</span> {message}
      </p>
      <Badge variant="warning">Review</Badge>
    </div>
  );
}
