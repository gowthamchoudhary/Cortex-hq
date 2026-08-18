import { useCallback, useEffect, useState } from "react";
import { Cable, Database } from "lucide-react";
import { fetchSources } from "@/api/sources";
import { PageHeader, EmptyState, ErrorState, LoadingState } from "@/components/shared/states";
import { useAuth } from "@/auth/AuthContext";
import { formatNumber, timeAgo } from "@/lib/format";
import type { SourcesResponse } from "@/types/api";

export function SourcesPage() {
  const { brains } = useAuth();
  const collection = brains[0]?.collection_name;
  const [data, setData] = useState<SourcesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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

  if (loading) return <LoadingState rows={4} />;
  if (error) return <ErrorState message={error} onRetry={() => void load()} />;
  if (!data) {
    return (
      <EmptyState
        title="No sources yet"
        message="Connect a source to start ingesting knowledge."
      />
    );
  }

  const sourceTypes = Object.entries(data.source_type_breakdown || {});

  return (
    <div className="space-y-8">
      <PageHeader
        title="Sources"
        subtitle={`${formatNumber(data.total_documents)} documents ingested`}
        actions={
          data.last_ingestion_timestamp ? (
            <span
              className="inline-flex items-center rounded-lg px-3 py-1 text-[12px] font-medium"
              style={{
                background: "hsl(var(--muted))",
                color: "hsl(var(--muted-foreground))",
              }}
            >
              Last ingestion {timeAgo(data.last_ingestion_timestamp)}
            </span>
          ) : undefined
        }
      />

      {sourceTypes.length === 0 ? (
        <EmptyState
          title="No connected sources"
          message="Your organization hasn't connected any sources yet. Source type breakdown will appear here after the first ingestion."
        />
      ) : (
        <div className="dash-card">
          <div className="dash-card-header">
            <div className="flex items-center gap-2">
              <Cable className="h-4 w-4 text-faint" />
              <p className="dash-card-title">Source types</p>
            </div>
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
