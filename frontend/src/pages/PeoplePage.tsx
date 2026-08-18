import { useCallback, useEffect, useState } from "react";
import { fetchPeople } from "@/api/people";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Avatar } from "@/components/ui/avatar";
import { PageHeader, EmptyState, ErrorState, LoadingState } from "@/components/shared/states";
import { useAuth } from "@/auth/AuthContext";
import { formatNumber } from "@/lib/format";
import type { Person } from "@/types/api";

const ROLE_VARIANT: Record<string, "default" | "accent" | "outline"> = {
  admin: "accent",
  member: "default",
  guest: "outline",
};

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
      setError(err instanceof Error ? err.message : "Failed to load the directory.");
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
        subtitle={items.length > 0 ? `${formatNumber(items.length)} people in the directory` : "Directory and access mapping"}
      />

      {items.length === 0 ? (
        <EmptyState
          title="No employees registered"
          message="People appear here once the employee directory is populated. Their Cortex role determines what knowledge each person can see."
        />
      ) : (
        <Card>
          <CardContent className="divide-y divide-border p-0">
            {items.map((person) => (
              <div key={person.employee_id} className="flex items-center gap-4 px-5 py-4">
                <Avatar name={person.name} />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[13.5px] font-medium text-foreground">
                    {person.name}
                    {person.role_title ? (
                      <span className="ml-2 font-normal text-faint">{person.role_title}</span>
                    ) : null}
                  </p>
                  <p className="mt-0.5 truncate text-[12px] text-muted-foreground">
                    {person.work_email}
                    {person.department ? ` · ${person.department}` : ""}
                  </p>
                </div>
                <div className="hidden items-center gap-1.5 md:flex">
                  {person.linked_platforms.map((platform) => (
                    <Badge key={platform} variant="outline" className="px-1.5 py-0 text-[10px] capitalize">
                      {platform}
                    </Badge>
                  ))}
                </div>
                <div className="shrink-0 text-right">
                  <Badge variant={ROLE_VARIANT[person.cortex_role] ?? "outline"}>
                    {person.cortex_role}
                  </Badge>
                  <p className="mt-1 text-[11px] text-faint">
                    {formatNumber(person.access_summary?.visible_documents ?? 0)} docs visible
                  </p>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
