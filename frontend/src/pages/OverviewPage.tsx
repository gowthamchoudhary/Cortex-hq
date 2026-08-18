import { useCallback, useEffect, useState } from "react";
import { Bot, Cable, Network, Users } from "lucide-react";
import { fetchOverview } from "@/api/overview";
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
      setError(
        err instanceof Error ? err.message : "Failed to load the overview."
      );
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
        <PageHeader
          title="Overview"
          subtitle="What's happening across your organization."
        />
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
      <PageHeader
        title="Overview"
        subtitle="Here's what's happening across your organization."
      />

      {/* Metric cards */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          icon={Cable}
          label="Connected sources"
          value={formatNumber(stats.total_documents)}
          hint={`${sourceTypes.length} source types`}
        />
        <MetricCard
          icon={Users}
          label="People"
          value={formatNumber(data.people_count)}
          hint="in the directory"
        />
        <MetricCard
          icon={Bot}
          label="Agents"
          value={formatNumber(data.agents_count)}
          hint="deployed"
        />
        <MetricCard
          icon={Network}
          label="Knowledge"
          value={formatNumber(stats.total_entities)}
          hint={`${formatNumber(stats.total_facts)} facts · ${formatNumber(
            stats.total_relations
          )} relations`}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* Needs attention */}
        <div className="dash-card">
          <div className="dash-card-header">
            <p className="dash-card-title">Needs attention</p>
          </div>
          <div className="dash-card-body">
            {stats.pending_merges || stats.disputed_facts ? (
              <div className="space-y-2.5">
                {stats.pending_merges > 0 ? (
                  <AttentionRow
                    count={stats.pending_merges}
                    message="entity merges awaiting review"
                  />
                ) : null}
                {stats.disputed_facts > 0 ? (
                  <AttentionRow
                    count={stats.disputed_facts}
                    message="facts marked as disputed"
                  />
                ) : null}
              </div>
            ) : (
              <p className="py-2 text-[13.5px] text-muted-foreground">
                Nothing needs attention right now.
              </p>
            )}
          </div>
        </div>

        {/* Sources */}
        <div className="dash-card">
          <div className="dash-card-header">
            <p className="dash-card-title">Sources</p>
            {stats.last_ingestion_timestamp ? (
              <span
                className="inline-flex items-center rounded-lg px-2 py-0.5 text-[11px] font-medium"
                style={{
                  background: "hsl(var(--muted))",
                  color: "hsl(var(--muted-foreground))",
                }}
              >
                {timeAgo(stats.last_ingestion_timestamp)}
              </span>
            ) : null}
          </div>
          <div className="dash-card-body space-y-3.5">
            {sourceTypes.length > 0 ? (
              sourceTypes.map(([type, count]) => {
                const max = Math.max(...sourceTypes.map(([, c]) => c), 1);
                return (
                  <div key={type}>
                    <div className="mb-1.5 flex items-center justify-between text-[13px]">
                      <span className="font-medium text-foreground capitalize">
                        {type}
                      </span>
                      <span className="text-muted-foreground">
                        {formatNumber(count)}
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
              })
            ) : (
              <p className="py-2 text-[13.5px] text-muted-foreground">
                No source types recorded yet.
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function MetricCard({
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
    <div className="metric-card">
      <div className="metric-label">
        <Icon />
        {label}
      </div>
      <p className="metric-value">{value}</p>
      <p className="metric-hint">{hint}</p>
    </div>
  );
}

function AttentionRow({ count, message }: { count: number; message: string }) {
  return (
    <div
      className="flex items-center justify-between rounded-xl px-4 py-3"
      style={{
        background: "hsl(38 92% 46% / 0.05)",
        border: "1px solid hsl(38 92% 46% / 0.12)",
      }}
    >
      <p className="text-[13.5px] text-foreground">
        <span className="font-semibold">{formatNumber(count)}</span>{" "}
        {message}
      </p>
      <span
        className="inline-flex items-center rounded-lg px-2 py-0.5 text-[11px] font-medium"
        style={{
          background: "hsl(38 92% 46% / 0.1)",
          color: "hsl(38 92% 46%)",
        }}
      >
        Review
      </span>
    </div>
  );
}
