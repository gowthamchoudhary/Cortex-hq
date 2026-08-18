import { useCallback, useEffect, useState } from "react";
import { ArrowDownToLine, Rocket } from "lucide-react";
import { fetchActivity } from "@/api/activity";
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
      setError(
        err instanceof Error ? err.message : "Failed to load activity."
      );
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
      <PageHeader
        title="Activity"
        subtitle="Recent ingestion and deployment events"
      />

      {items.length === 0 ? (
        <EmptyState
          title="No activity yet"
          message="Ingestion and agent deployment events will show up here over time."
        />
      ) : (
        <div className="dash-card overflow-hidden">
          {items.map((event) => (
            <div key={event.id} className="list-item">
              <div className="list-item-icon">
                {event.kind === "deployment" ? (
                  <Rocket className="h-4 w-4" />
                ) : (
                  <ArrowDownToLine className="h-4 w-4" />
                )}
              </div>
              <div className="list-item-content">
                <p className="list-item-title" title={event.title}>
                  {event.title}
                </p>
                <div className="list-item-meta">
                  <span className="capitalize">{event.kind}</span>
                </div>
              </div>
              <span className="shrink-0 text-[12px] text-faint">
                {timeAgo(event.created_at)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
