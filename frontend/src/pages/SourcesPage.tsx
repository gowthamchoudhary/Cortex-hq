import { useCallback, useEffect, useState } from "react";
import { Cable } from "lucide-react";
import { fetchSources } from "@/api/sources";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
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
      setError(err instanceof Error ? err.message : "Failed to load sources.");
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
    return <EmptyState title="No sources yet" message="Connect a source to start ingesting knowledge." />;
  }

  const sourceTypes = Object.entries(data.source_type_breakdown || {});

  return (
    <div className="space-y-8">
      <PageHeader
        title="Sources"
        subtitle={`${formatNumber(data.total_documents)} documents ingested`}
        actions={
          data.last_ingestion_timestamp ? (
            <Badge variant="outline">Last ingestion {timeAgo(data.last_ingestion_timestamp)}</Badge>
          ) : undefined
        }
      />

      {sourceTypes.length === 0 ? (
        <EmptyState
          title="No connected sources"
          message="Source type breakdown will appear here after the first ingestion."
        />
      ) : (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Cable className="h-4 w-4 text-faint" /> Source types
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {sourceTypes.map(([type, count]) => {
              const max = Math.max(...sourceTypes.map(([, c]) => c), 1);
              return (
                <div key={type}>
                  <div className="mb-1.5 flex items-center justify-between text-[13.5px]">
                    <span className="font-medium capitalize text-foreground">{type}</span>
                    <span className="text-muted-foreground">{formatNumber(count)} documents</span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-muted">
                    <div
                      className="h-full rounded-full bg-accent/70"
                      style={{ width: `${Math.round((count / max) * 100)}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
