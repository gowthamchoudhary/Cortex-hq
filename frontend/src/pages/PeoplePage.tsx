import { useCallback, useEffect, useState } from "react";
import { Mail, Building2 } from "lucide-react";
import { fetchPeople } from "@/api/people";
import { PageHeader, EmptyState, ErrorState, LoadingState } from "@/components/shared/states";
import { useAuth } from "@/auth/AuthContext";
import { formatNumber, initialsFor } from "@/lib/format";
import type { Person } from "@/types/api";

export function PeoplePage() {
  const { brains } = useAuth();
  const collection = brains[0]?.collection_name;
  const [items, setItems] = useState<Person[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetchPeople(collection);
      setItems(response.items);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to load the directory."
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
        title="People & Access"
        subtitle={
          items.length > 0
            ? `${formatNumber(items.length)} people in the directory`
            : "Directory and access mapping"
        }
      />

      {items.length === 0 ? (
        <EmptyState
          title="No employees registered"
          message="People appear here once the employee directory is populated. Their Cortex role determines what knowledge each person can see."
        />
      ) : (
        <div className="dash-card overflow-hidden">
          {items.map((person) => (
            <div key={person.employee_id} className="list-item">
              <div
                className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-[12px] font-bold"
                style={{
                  background:
                    "linear-gradient(135deg, hsl(var(--accent) / 0.12), hsl(var(--accent) / 0.06))",
                  color: "hsl(var(--accent))",
                }}
              >
                {initialsFor(person.name)}
              </div>
              <div className="min-w-0 flex-1">
                <p className="list-item-title">
                  {person.name}
                  {person.role_title ? (
                    <span className="ml-2 font-normal text-faint">
                      {person.role_title}
                    </span>
                  ) : null}
                </p>
                <div className="list-item-meta">
                  <Mail className="h-3 w-3" />
                  <span>{person.work_email}</span>
                  {person.department ? (
                    <>
                      <Building2 className="h-3 w-3" />
                      <span>{person.department}</span>
                    </>
                  ) : null}
                </div>
              </div>
              <div className="hidden items-center gap-1.5 md:flex">
                {person.linked_platforms.map((platform) => (
                  <span
                    key={platform}
                    className="inline-flex items-center rounded-md border border-border px-1.5 py-0.5 text-[10px] font-medium capitalize"
                  >
                    {platform}
                  </span>
                ))}
              </div>
              <div className="shrink-0 text-right">
                <span
                  className="inline-flex items-center rounded-lg px-2 py-0.5 text-[11px] font-medium capitalize"
                  style={{
                    background:
                      person.cortex_role === "admin"
                        ? "hsl(var(--accent) / 0.1)"
                        : "hsl(var(--muted))",
                    color:
                      person.cortex_role === "admin"
                        ? "hsl(var(--accent))"
                        : "hsl(var(--muted-foreground))",
                  }}
                >
                  {person.cortex_role}
                </span>
                <p className="mt-1 text-[11px] text-faint">
                  {formatNumber(
                    person.access_summary?.visible_documents ?? 0
                  )}{" "}
                  docs visible
                </p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
