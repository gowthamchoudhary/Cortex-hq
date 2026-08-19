import { useCallback, useEffect, useState } from "react";
import {
  Bot,
  Plus,
  Slack,
  Github,
  Mail,
  Loader2,
  CheckCircle2,
  Settings,
  ExternalLink,
} from "lucide-react";
import { fetchAgents, createAgent, deployAgent } from "@/api/agents";
import { PageHeader, EmptyState, ErrorState, LoadingState } from "@/components/shared/states";
import { useAuth } from "@/auth/AuthContext";
import { timeAgo } from "@/lib/format";
import type { Agent } from "@/types/api";

const PLATFORM_CONFIG: Record<
  string,
  { label: string; icon: typeof Slack; fields: { key: string; label: string; placeholder: string }[] }
> = {
  slack: {
    label: "Slack",
    icon: Slack,
    fields: [
      { key: "workspace", label: "Workspace name", placeholder: "e.g. acme-corp" },
      { key: "webhook_url", label: "Webhook URL", placeholder: "https://hooks.slack.com/services/..." },
      { key: "bot_token", label: "Bot token (xoxb-...)", placeholder: "xoxb-..." },
    ],
  },
  github: {
    label: "GitHub",
    icon: Github,
    fields: [
      { key: "repo", label: "Repository (owner/name)", placeholder: "e.g. facebook/react" },
      { key: "bot_username", label: "Bot username", placeholder: "e.g. cortex-bot" },
    ],
  },
  email: {
    label: "Email",
    icon: Mail,
    fields: [
      { key: "from_address", label: "From address", placeholder: "cortex@yourcompany.com" },
      { key: "imap_host", label: "IMAP host", placeholder: "imap.gmail.com" },
    ],
  },
};

export function AgentsPage() {
  const { selectedBrain } = useAuth();
  const collection = selectedBrain;
  const [items, setItems] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);

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

  const handleCreate = async (agentName: string, roleDefault: string) => {
    await createAgent({ collection, agentName, roleDefault });
    setShowCreate(false);
    await load();
  };

  const handleDeploy = async (
    agentId: string,
    platform: "slack" | "github" | "email",
    config: Record<string, unknown>
  ) => {
    await deployAgent({ agentId, platform, config });
    await load();
  };

  if (loading) return <LoadingState rows={3} />;
  if (error) return <ErrorState message={error} onRetry={() => void load()} />;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Agents"
        subtitle={
          items.length > 0
            ? `${items.length} configured agent${items.length === 1 ? "" : "s"}`
            : "Create agents to let your team ask Cortex from any platform"
        }
        actions={
          <button
            type="button"
            onClick={() => setShowCreate(!showCreate)}
            className="inline-flex items-center gap-2 rounded-xl px-4 py-2 text-[13px] font-medium text-white transition-all duration-200"
            style={{
              background: "linear-gradient(180deg, #252525 0%, #171717 100%)",
              boxShadow:
                "0 1px 2px rgba(0,0,0,0.15), inset 0 1px 0 rgba(255,255,255,0.08)",
              border: "1px solid rgba(255,255,255,0.10)",
            }}
          >
            <Plus className="h-4 w-4" />
            Create agent
          </button>
        }
      />

      {/* Create Agent Form */}
      {showCreate && (
        <CreateAgentForm
          onSubmit={handleCreate}
          onCancel={() => setShowCreate(false)}
        />
      )}

      {/* Agent Cards */}
      {items.length === 0 ? (
        <EmptyState
          title="No agents configured yet"
          message="Agents let your team ask Cortex questions from Slack, GitHub, and email. Create one above to get started."
        />
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {items.map((agent) => (
            <AgentCard
              key={agent.agent_id}
              agent={agent}
              onDeploy={handleDeploy}
            />
          ))}
        </div>
      )}
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Create Agent Form                                                           */
/* -------------------------------------------------------------------------- */

function CreateAgentForm({
  onSubmit,
  onCancel,
}: {
  onSubmit: (agentName: string, roleDefault: string) => Promise<void>;
  onCancel: () => void;
}) {
  const [name, setName] = useState("");
  const [role, setRole] = useState("member");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setLoading(true);
    setError(null);
    try {
      await onSubmit(name.trim(), role);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create agent.");
      setLoading(false);
    }
  };

  return (
    <div className="rounded-2xl bg-white border border-black/[0.065] shadow-[0_4px_20px_rgba(0,0,0,0.035)] p-6">
      <div className="flex items-center justify-between mb-5">
        <h3 className="text-[16px] font-semibold text-[#171717]">
          Create a new agent
        </h3>
        <button
          type="button"
          onClick={onCancel}
          className="text-[13px] text-[#6B6B6B] hover:text-[#171717] transition-colors"
        >
          Cancel
        </button>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block mb-1 text-[13px] font-medium text-[#171717]">
            Agent name
          </label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Support Bot"
            className="w-full rounded-xl border border-black/[0.08] bg-[#FAFAF9] px-4 py-3 text-[14px] text-[#171717] placeholder:text-[#9A9A9A] outline-none transition-all duration-200 focus:border-[#171717]/20 focus:ring-2 focus:ring-[#171717]/5"
            autoFocus
            disabled={loading}
          />
        </div>

        <div>
          <label className="block mb-1 text-[13px] font-medium text-[#171717]">
            Default role
          </label>
          <select
            value={role}
            onChange={(e) => setRole(e.target.value)}
            disabled={loading}
            className="w-full rounded-xl border border-black/[0.08] bg-[#FAFAF9] px-4 py-3 text-[14px] text-[#171717] outline-none transition-all duration-200 focus:border-[#171717]/20 focus:ring-2 focus:ring-[#171717]/5"
          >
            <option value="member">Member — can see internal knowledge</option>
            <option value="admin">Admin — full access</option>
            <option value="guest">Guest — public knowledge only</option>
          </select>
        </div>

        {error && (
          <p className="text-[13px] text-[#EF4444]">{error}</p>
        )}

        <button
          type="submit"
          disabled={loading || !name.trim()}
          className="w-full flex items-center justify-center gap-2 rounded-xl px-5 py-3 text-[14px] font-medium text-white transition-all duration-200 disabled:opacity-40"
          style={{
            background: "linear-gradient(180deg, #252525 0%, #171717 100%)",
            boxShadow:
              "0 1px 2px rgba(0,0,0,0.15), inset 0 1px 0 rgba(255,255,255,0.08)",
            border: "1px solid rgba(255,255,255,0.10)",
          }}
        >
          {loading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            "Create agent"
          )}
        </button>
      </form>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Agent Card                                                                  */
/* -------------------------------------------------------------------------- */

function AgentCard({
  agent,
  onDeploy,
}: {
  agent: Agent;
  onDeploy: (
    agentId: string,
    platform: "slack" | "github" | "email",
    config: Record<string, unknown>
  ) => Promise<void>;
}) {
  const [deployingPlatform, setDeployingPlatform] = useState<string | null>(null);
  const [deployConfig, setDeployConfig] = useState<Record<string, string>>({});
  const [deployError, setDeployError] = useState<string | null>(null);

  const deployedPlatforms = new Set(
    agent.deployments.map((d) => d.platform)
  );

  const handleDeploy = async (platform: "slack" | "github" | "email") => {
    setDeployError(null);
    setDeployingPlatform(platform);

    try {
      await onDeploy(agent.agent_id, platform, deployConfig);
      setDeployConfig({});
      setDeployingPlatform(null);
    } catch (err) {
      setDeployError(
        err instanceof Error ? err.message : "Deploy failed."
      );
      setDeployingPlatform(null);
    }
  };

  return (
    <div className="dash-card">
      <div className="p-5">
        {/* Agent Header */}
        <div className="flex items-start gap-3 mb-4">
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
              {agent.collection} · {timeAgo(agent.created_at)}
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

        {/* Existing Deployments */}
        {agent.deployments.length > 0 && (
          <div className="mb-4 space-y-2">
            {agent.deployments.map((deployment) => {
              const platformInfo = PLATFORM_CONFIG[deployment.platform];
              const Icon = platformInfo?.icon || Settings;
              return (
                <div
                  key={deployment.platform}
                  className="flex items-center gap-2.5 rounded-xl border border-black/[0.065] bg-[#FAFAF9] px-3 py-2.5"
                >
                  <Icon className="h-4 w-4 text-[#6B6B6B]" />
                  <span className="text-[13px] font-medium text-[#171717]">
                    {platformInfo?.label ?? deployment.platform}
                  </span>
                  <span
                    className={`inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[10px] font-medium ${
                      deployment.status === "active"
                        ? "bg-[#10B981]/10 text-[#10B981]"
                        : "bg-[#F59E0B]/10 text-[#F59E0B]"
                    }`}
                  >
                    <span
                      className={`h-1.5 w-1.5 rounded-full ${
                        deployment.status === "active"
                          ? "bg-[#10B981]"
                          : "bg-[#F59E0B]"
                      }`}
                    />
                    {deployment.status}
                  </span>
                </div>
              );
            })}
          </div>
        )}

        {/* Deploy Options */}
        <div className="border-t border-black/[0.065] pt-4">
          <p className="text-[12px] font-medium text-[#6B6B6B] uppercase tracking-wider mb-3">
            Deploy to platform
          </p>
          <div className="grid grid-cols-3 gap-2">
            {(["slack", "github", "email"] as const).map((platform) => {
              const info = PLATFORM_CONFIG[platform];
              const Icon = info.icon;
              const isDeployed = deployedPlatforms.has(platform);
              const isDeploying = deployingPlatform === platform;

              return (
                <button
                  key={platform}
                  type="button"
                  onClick={() => {
                    if (!isDeployed) {
                      setDeployingPlatform(
                        deployingPlatform === platform ? null : platform
                      );
                      setDeployConfig({});
                      setDeployError(null);
                    }
                  }}
                  disabled={isDeployed}
                  className={`flex flex-col items-center gap-1.5 rounded-xl border p-3 text-[12px] font-medium transition-all duration-200 ${
                    isDeployed
                      ? "border-[#10B981]/20 bg-[#10B981]/[0.03] text-[#10B981] cursor-default"
                      : isDeploying
                        ? "border-[#171717]/20 bg-[#171717]/[0.03] shadow-sm"
                        : "border-black/[0.065] hover:border-black/[0.12] hover:shadow-[0_2px_8px_rgba(0,0,0,0.04)]"
                  }`}
                >
                  <Icon className="h-5 w-5" />
                  <span>{info.label}</span>
                  {isDeployed && (
                    <CheckCircle2 className="h-3.5 w-3.5" />
                  )}
                </button>
              );
            })}
          </div>
        </div>

        {/* Deploy Form */}
        {deployingPlatform && PLATFORM_CONFIG[deployingPlatform] && (
          <div className="mt-4 rounded-xl border border-black/[0.065] bg-[#FAFAF9] p-4 space-y-3">
            <p className="text-[13px] font-medium text-[#171717]">
              Configure {PLATFORM_CONFIG[deployingPlatform].label} deployment
            </p>
            {PLATFORM_CONFIG[deployingPlatform].fields.map((field) => (
              <div key={field.key}>
                <label className="block mb-1 text-[12px] font-medium text-[#6B6B6B]">
                  {field.label}
                </label>
                <input
                  type="text"
                  value={deployConfig[field.key] || ""}
                  onChange={(e) =>
                    setDeployConfig({
                      ...deployConfig,
                      [field.key]: e.target.value,
                    })
                  }
                  placeholder={field.placeholder}
                  className="w-full rounded-lg border border-black/[0.08] bg-white px-3 py-2 text-[13px] text-[#171717] placeholder:text-[#9A9A9A] outline-none transition-all duration-200 focus:border-[#171717]/20 focus:ring-1 focus:ring-[#171717]/5"
                />
              </div>
            ))}

            {deployError && (
              <p className="text-[12px] text-[#EF4444]">{deployError}</p>
            )}

            <div className="flex items-center gap-2 pt-1">
              <button
                type="button"
                onClick={() => {
                  void handleDeploy(deployingPlatform as "slack" | "github" | "email");
                }}
                disabled={
                  deployingPlatform !== null &&
                  PLATFORM_CONFIG[deployingPlatform].fields.some(
                    (f) => !deployConfig[f.key]?.trim()
                  )
                }
                className="flex items-center gap-2 rounded-lg px-4 py-2 text-[13px] font-medium text-white transition-all duration-200 disabled:opacity-40"
                style={{
                  background: "linear-gradient(180deg, #252525 0%, #171717 100%)",
                  boxShadow:
                    "0 1px 2px rgba(0,0,0,0.15), inset 0 1px 0 rgba(255,255,255,0.08)",
                  border: "1px solid rgba(255,255,255,0.10)",
                }}
              >
                <ExternalLink className="h-3.5 w-3.5" />
                Save configuration
              </button>
              <button
                type="button"
                onClick={() => {
                  setDeployingPlatform(null);
                  setDeployConfig({});
                }}
                className="rounded-lg px-4 py-2 text-[13px] font-medium text-[#6B6B6B] hover:text-[#171717] transition-colors"
              >
                Cancel
              </button>
            </div>

            <p className="text-[11px] text-[#9A9A9A]">
              Configuration saved as pending. Follow the platform-specific setup
              instructions to go live.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
