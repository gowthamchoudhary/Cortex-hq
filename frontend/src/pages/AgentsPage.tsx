import { useCallback, useEffect, useState } from "react";
import { Bot } from "lucide-react";
import { fetchAgents } from "@/api/agents";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Avatar } from "@/components/ui/avatar";
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
      setError(err instanceof Error ? err.message : "Failed to load agents.");
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
        subtitle={items.length > 0 ? `${items.length} deployed agents` : "Deploy agents to your platforms"}
      />

      {items.length === 0 ? (
        <EmptyState
          title="No agents yet"
          message="Agents let your team ask Cortex from Slack, GitHub, email, and WhatsApp. They'll appear here once created."
        />
      ) : (
        <div className="grid gap-3 lg:grid-cols-2">
          {items.map((agent) => (
            <Card key={agent.agent_id}>
              <CardHeader className="flex-row items-center justify-between space-y-0">
                <div className="flex items-center gap-3">
                  <Avatar name={agent.agent_name} />
                  <div>
                    <CardTitle className="text-[14px]">{agent.agent_name}</CardTitle>
                    <p className="mt-0.5 text-[12px] text-faint">collection · {agent.collection}</p>
                  </div>
                </div>
                <Badge variant="outline">{agent.role_default}</Badge>
              </CardHeader>
              <CardContent>
                {agent.deployments.length > 0 ? (
                  <div className="flex flex-wrap gap-1.5">
                    {agent.deployments.map((deployment) => (
                      <Badge
                        key={deployment.platform}
                        variant={deployment.status === "active" ? "success" : "default"}
                      >
                        <Bot className="h-3 w-3" />
                        {PLATFORM_LABELS[deployment.platform] ?? deployment.platform} ·{" "}
                        {deployment.status}
                      </Badge>
                    ))}
                  </div>
                ) : (
                  <p className="text-[12.5px] text-faint">
                    Created {timeAgo(agent.created_at)} · not deployed yet
                  </p>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
