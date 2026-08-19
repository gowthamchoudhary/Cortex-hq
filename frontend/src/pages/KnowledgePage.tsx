import { useCallback, useEffect, useState } from "react";
import { Search, Database } from "lucide-react";
import { fetchKnowledge } from "@/api/knowledge";
import { Input } from "@/components/ui/input";
import { PageHeader, EmptyState, ErrorState, LoadingState } from "@/components/shared/states";
import { useAuth } from "@/auth/AuthContext";
import { cn } from "@/lib/utils";
import { formatNumber, timeAgo } from "@/lib/format";
import type { KnowledgeItem } from "@/types/api";

const TYPE_FILTERS = [
  { value: "", label: "All" },
  { value: "entity", label: "Entities" },
  { value: "factstate", label: "Facts" },
  { value: "relation", label: "Relations" },
  { value: "document", label: "Documents" },
];

export function KnowledgePage() {
  const { selectedBrain } = useAuth();
  const collection = selectedBrain;
  const [query, setQuery] = useState("");
  const [type, setType] = useState("");
  const [items, setItems] = useState<KnowledgeItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    async (search = query, recordType = type) => {
      setLoading(true);
      setError(null);
      try {
        const response = await fetchKnowledge({
          collection,
          q: search || undefined,
          type: recordType || undefined,
        });
        setItems(response.items);
        setTotal(response.total);
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Failed to load knowledge."
        );
      } finally {
        setLoading(false);
      }
    },
    [collection, query, type]
  );

  useEffect(() => {
    void load("", "");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [collection]);

  return (
    <div>
      <PageHeader
        title="Knowledge"
        subtitle={
          total > 0
            ? `${formatNumber(total)} records in ${collection || "your brain"}`
            : "Browse what Cortex knows"
        }
      />

      <div className="mb-6 flex flex-wrap items-center gap-2">
        <div className="relative w-full max-w-xs">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-faint" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") void load(query, type);
            }}
            placeholder="Search knowledge..."
            className="pl-9"
          />
        </div>
        <div className="flex items-center gap-1">
          {TYPE_FILTERS.map((filter) => (
            <button
              key={filter.value}
              type="button"
              className={cn(
                "dash-btn dash-btn-ghost text-[12.5px]",
                type === filter.value && "!bg-muted !text-foreground"
              )}
              onClick={() => {
                setType(filter.value);
                void load(query, filter.value);
              }}
            >
              {filter.label}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <LoadingState rows={6} />
      ) : error ? (
        <ErrorState message={error} onRetry={() => void load()} />
      ) : items.length === 0 ? (
        <EmptyState
          title="No knowledge records"
          message="Nothing matches this search yet. Records appear here once sources are ingested into the graph."
        />
      ) : (
        <div className="dash-card overflow-hidden">
          {items.map((item, i) => (
            <div key={item.id} className={cn("list-item", i === 0 && "border-t-0")}>
              <div className="list-item-icon">
                <Database className="h-4 w-4" />
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
                  {item.confidence !== undefined &&
                  item.confidence !== null ? (
                    <span>{Math.round(item.confidence * 100)}% conf.</span>
                  ) : null}
                  <span className="ml-auto shrink-0">
                    {timeAgo(item.created_at)}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
