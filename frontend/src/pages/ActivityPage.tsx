import { useCallback, useEffect, useState } from "react";
import { ArrowDownToLine, Rocket } from "lucide-react";
import { fetchActivity } from "@/api/activity";
import { Card, CardContent } from "@/components/ui/card";
import { PageHeader, EmptyState, ErrorState, LoadingState } from "@/components/shared/states";
import { useAuth } from "@/auth/AuthContext";
import { timeAgo } from "@/lib/format";
import type { ActivityEvent } from "@/types/api";

export function ActivityPage() {
  const { brains } = useAuth();
  const collection = brains[0]?.collection_name;
  const [items, setItems] = useState<ActivityEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetchActivity(collection);
      setItems(response.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load activity.");
    } finally {
      setLoading(false);
    }
  }, [collection]);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) return <LoadingState rows={6} />;
  if (error) return <ErrorState message={error} onRetry={() => void load()} />;

  return (
    <div>
      <PageHeader title="Activity" subtitle="Recent ingestion and deployment events" />

      {items.length === 0 ? (
        <EmptyState
          title="No activity yet"
          message="Ingestion and agent deployment events will show up here over time."
        />
      ) : (
        <Card>
          <CardContent className="divide-y divide-border p-0">
            {items.map((event) => (
              <div key={event.id} className="flex items-center gap-4 px-5 py-3.5">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground">
                  {event.kind === "deployment" ? (
                    <Rocket className="h-4 w-4" />
                  ) : (
                    <ArrowDownToLine className="h-4 w-4" />
                  )}
                </div>
                <p className="min-w-0 flex-1 truncate text-[13.5px] text-foreground" title={event.title}>
                  {event.title}
                </p>
                <span className="shrink-0 text-[12px] text-faint">{timeAgo(event.created_at)}</span>
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
