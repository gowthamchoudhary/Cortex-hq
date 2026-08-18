import { useCallback, useEffect, useState } from "react";
import { Bot, Clock } from "lucide-react";
import { fetchAgents } from "@/api/agents";
import { PageHeader, EmptyState, ErrorState, LoadingState } from "@/components/shared/states";
import { timeAgo } from "@/lib/format";
import type { Agent } from "@/types/api";

const PLATFORM_LABELS: Record<string, string> = {
  slack: "Slack",
  github: "GitHub",
  email: "Email",
  whatsapp: "WhatsApp",
};

export function AgentsPage() {
  const [items, setItems] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetchAgents();
      setItems(response.items);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load agents."
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) return <LoadingState rows={3} />;
  if (error) return <ErrorState message={error} onRetry={() => void load()} />;

  return (
    <div>
      <PageHeader
        title="Agents"
        subtitle={
          items.length > 0
            ? `${items.length} deployed agents`
            : "Deploy agents to your platforms"
        }
      />

      {items.length === 0 ? (
        <EmptyState
          title="No agents deployed yet"
          message="Agents let your team ask Cortex from Slack, GitHub, email, and WhatsApp. They'll appear here once created."
        />
      ) : (
        <div className="grid gap-3 lg:grid-cols-2">
          {items.map((agent) => (
            <div key={agent.agent_id} className="dash-card">
              <div className="p-5">
                <div className="flex items-start gap-3">
                  <div
                    className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl"
                    style={{ background: "hsl(var(--accent) / 0.08)" }}
                  >
                    <Bot
                      className="h-5 w-5"
                      style={{ color: "hsl(var(--accent))" }}
                    />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-[14.5px] font-semibold text-foreground">
                      {agent.agent_name}
                    </p>
                    <p className="mt-0.5 text-[12px] text-faint">
                      collection · {agent.collection}
                    </p>
                  </div>
                  <span
                    className="inline-flex items-center rounded-lg px-2 py-0.5 text-[11px] font-medium capitalize"
                    style={{
                      background: "hsl(var(--muted))",
                      color: "hsl(var(--muted-foreground))",
                    }}
                  >
                    {agent.role_default}
                  </span>
                </div>

                <div className="mt-4">
                  {agent.deployments.length > 0 ? (
                    <div className="flex flex-wrap gap-2">
                      {agent.deployments.map((deployment) => (
                        <div
                          key={deployment.platform}
                          className="inline-flex items-center gap-1.5 rounded-lg border border-border px-2.5 py-1.5 text-[12px]"
                        >
                          <span
                            className="h-2 w-2 rounded-full"
                            style={{
                              background:
                                deployment.status === "active"
                                  ? "hsl(var(--success))"
                                  : "hsl(var(--faint))",
                            }}
                          />
                          <span className="font-medium text-foreground">
                            {PLATFORM_LABELS[deployment.platform] ??
                              deployment.platform}
                          </span>
                          <span className="text-faint capitalize">
                            {deployment.status}
                          </span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="flex items-center gap-2 text-[12.5px] text-faint">
                      <Clock className="h-3.5 w-3.5" />
                      Created {timeAgo(agent.created_at)} · not deployed yet
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
