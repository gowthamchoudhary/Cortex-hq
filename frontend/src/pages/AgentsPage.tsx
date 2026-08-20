import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Plus,
  Loader2,
  CheckCircle2,
  ExternalLink,
} from "lucide-react";
import { SiGithub, SiGmail } from "@icons-pack/react-simple-icons";

/* Slack isn't in @icons-pack — hand-crafted multi-color mark */
function SlackIcon({ size = 20 }: { size?: number }) {
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} fill="none">
      <path d="M5.042 15.165a2.528 2.528 0 0 1-2.52 2.523A2.528 2.528 0 0 1 0 15.165a2.527 2.527 0 0 1 2.522-2.52h2.52v2.52z" fill="#E01E5A"/>
      <path d="M6.313 15.165a2.527 2.527 0 0 1 2.521-2.52 2.527 2.527 0 0 1 2.521 2.52v6.313A2.528 2.528 0 0 1 8.834 24a2.528 2.528 0 0 1-2.521-2.522v-6.313z" fill="#36C5F0"/>
      <path d="M6.313 8.834a2.527 2.527 0 0 1-2.521-2.52A2.528 2.528 0 0 1 6.313 3.79a2.527 2.527 0 0 1 2.521 2.522v2.522H6.313z" fill="#2EB67D"/>
      <path d="M8.834 6.313a2.528 2.528 0 0 1 2.521-2.521 2.528 2.528 0 0 1 2.521 2.521V8.83a2.528 2.528 0 0 1-2.521 2.521 2.527 2.527 0 0 1-2.521-2.52V6.313z" fill="#ECB22E"/>
      <path d="M15.165 6.313a2.528 2.528 0 0 1 2.523-2.521A2.528 2.528 0 0 1 20.21 6.313a2.527 2.527 0 0 1-2.522 2.52h-2.523V6.313z" fill="#36C5F0"/>
      <path d="M17.688 8.834a2.528 2.528 0 0 1 2.523 2.521 2.527 2.527 0 0 1-2.523 2.521h-6.312A2.528 2.528 0 0 1 8.834 11.355a2.528 2.528 0 0 1 2.52-2.521h6.312z" fill="#2EB67D"/>
      <path d="M15.165 17.688a2.527 2.527 0 0 1 2.523 2.523A2.528 2.528 0 0 1 15.165 22.73a2.527 2.527 0 0 1-2.52-2.52v-2.522h2.52z" fill="#E01E5A"/>
      <path d="M12.643 17.688a2.528 2.528 0 0 1-2.521 2.523 2.527 2.527 0 0 1-2.521-2.523v-6.312A2.528 2.528 0 0 1 10.122 8.834a2.527 2.527 0 0 1 2.521 2.521v6.313z" fill="#ECB22E"/>
      <path d="M8.834 15.165a2.528 2.528 0 0 1-2.521 2.523A2.527 2.527 0 0 1 3.79 15.165a2.528 2.528 0 0 1 2.522-2.52h2.522v2.52z" fill="#36C5F0"/>
    </svg>
  );
}
import { fetchAgents, createAgent, deployAgent, fetchSlackBotStatus, buildSlackInstallUrl } from "@/api/agents";
import { PageHeader, EmptyState, ErrorState, LoadingState } from "@/components/shared/states";
import { useAuth } from "@/auth/AuthContext";
import { timeAgo } from "@/lib/format";
import type { Agent } from "@/types/api";

const PLATFORMS = [
  {
    key: "slack" as const,
    label: "Slack",
    icon: SlackIcon,
    color: "#E01E5A",
    oauth: true,  // uses OAuth install, not manual token paste
  },
  {
    key: "github" as const,
    label: "GitHub",
    icon: SiGithub,
    color: "#7C3AED",
    oauth: false,
    instruction: [
      "1. Go to github.com/settings/tokens → Generate new token (classic)",
      "2. Select scopes: repo, read:org",
      "3. Copy the token",
      "4. Paste it below",
    ],
    inputLabel: "Personal access token",
    inputPlaceholder: "ghp_...",
  },
  {
    key: "email" as const,
    label: "Email",
    icon: SiGmail,
    color: "#EA4335",
    oauth: false,
    instruction: [
      "1. Configure an IMAP-capable email address for Cortex",
      "2. Ensure IMAP access is enabled (Gmail: App Passwords → IMAP)",
      "3. Paste the email address below",
    ],
    inputLabel: "Email address",
    inputPlaceholder: "cortex@yourcompany.com",
  },
];

export function AgentsPage() {
  const { selectedBrain } = useAuth();
  const collection = selectedBrain;
  const [items, setItems] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [slackConnected, setSlackConnected] = useState(false);

  // Detect OAuth success/error from URL params (after Slack install redirect).
  const urlParams = useMemo(() => {
    if (typeof window === "undefined") return new URLSearchParams();
    return new URLSearchParams(window.location.search);
  }, []);
  const oauthSuccess = urlParams.get("oauth_success");
  const oauthError = urlParams.get("oauth_error");

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

  // Check Slack bot token status.
  const checkSlackStatus = useCallback(async () => {
    try {
      const status = await fetchSlackBotStatus(collection);
      setSlackConnected(status.connected);
    } catch {
      setSlackConnected(false);
    }
  }, [collection]);

  useEffect(() => {
    void load();
    void checkSlackStatus();
  }, [load, checkSlackStatus]);

  // Clean up OAuth params from URL after processing.
  useEffect(() => {
    if (oauthSuccess || oauthError) {
      window.history.replaceState({}, "", window.location.pathname);
      // Re-check Slack status after a successful OAuth flow.
      if (oauthSuccess === "slack") {
        void checkSlackStatus();
      }
    }
  }, [oauthSuccess, oauthError, checkSlackStatus]);

  const handleCreate = async (agentName: string, roleDefault: string) => {
    await createAgent({ collection, agentName, roleDefault });
    setShowCreate(false);
    try {
      await load();
    } catch {
      // load() errors are already handled inside load()
    }
  };

  const handleDeploy = async (
    agentId: string,
    platform: "slack" | "github" | "email",
    config: Record<string, unknown>
  ) => {
    await deployAgent({ agentId, platform, config });
    await load();
    // Re-check Slack status after deploying to Slack.
    if (platform === "slack") {
      void checkSlackStatus();
    }
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
             className="btn-dark"
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
          message="Agents let your team ask Cortex questions from Slack, GitHub, and email."
        />
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {items.map((agent) => (
            <AgentCard
              key={agent.agent_id}
              agent={agent}
              onDeploy={handleDeploy}
              slackConnected={slackConnected}
              collection={collection}
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
    } finally {
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
            <option value="member">Member</option>
            <option value="admin">Admin</option>
            <option value="guest">Guest</option>
          </select>
          <p className="mt-1.5 text-[12px] text-[#6B6B6B] leading-relaxed">
            {role === "member" && "Member — agent shares internal knowledge with anyone who messages it, unless they're linked to an employee with a different role."}
            {role === "admin" && "Admin — agent has full access to all organizational knowledge and can answer questions across every access level."}
            {role === "guest" && "Guest — agent only answers from publicly available knowledge. Internal documents, private facts, and restricted data are excluded."}
          </p>
        </div>

        {error && <p className="text-[13px] text-[#EF4444]">{error}</p>}

        <button
          type="submit"
          disabled={loading || !name.trim()}
          className={`w-full ${loading ? "btn-green" : "btn-dark"}`}
        >
          {loading ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Creating…
            </>
          ) : (
            "Create agent"
          )}
        </button>
      </form>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Agent Card — with orb and one-click deploy per platform                     */
/* -------------------------------------------------------------------------- */

function AgentCard({
  agent,
  onDeploy,
  slackConnected,
  collection,
}: {
  agent: Agent;
  onDeploy: (
    agentId: string,
    platform: "slack" | "github" | "email",
    config: Record<string, unknown>
  ) => Promise<void>;
  slackConnected: boolean;
  collection?: string;
}) {
  const [deployingPlatform, setDeployingPlatform] = useState<string | null>(null);
  const [token, setToken] = useState("");
  const [emailConfig, setEmailConfig] = useState({
    from_address: "",
    smtp_host: "",
    smtp_port: "587",
    smtp_user: "",
    smtp_password: "",
  });
  const [deployError, setDeployError] = useState<string | null>(null);
  const [deploySuccess, setDeploySuccess] = useState<string | null>(null);

  const deployedPlatforms = new Set(agent.deployments.map((d) => d.platform));

  const handleDeploy = async (platform: "slack" | "github" | "email") => {
    setDeployError(null);
    setDeploySuccess(null);
    setDeployingPlatform(platform);

    const platformInfo = PLATFORMS.find((p) => p.key === platform)!;

    try {
      let config: Record<string, unknown>;
      if (platform === "email") {
        config = {
          from_address: emailConfig.from_address.trim(),
          smtp_host: emailConfig.smtp_host.trim(),
          smtp_port: parseInt(emailConfig.smtp_port) || 587,
          smtp_user: emailConfig.smtp_user.trim(),
          smtp_password: emailConfig.smtp_password,
          source: "per-organization",
        };
      } else {
        config = { token: token.trim() };
      }

      await onDeploy(agent.agent_id, platform, config);
      setDeploySuccess(`${platformInfo.label} configuration saved — see setup instructions to go live.`);
      setToken("");
      setDeployingPlatform(null);
      setTimeout(() => {
        setDeployingPlatform(null);
        setDeploySuccess(null);
      }, 3000);
    } catch (err) {
      setDeployError(
        err instanceof Error ? err.message : "Deploy failed."
      );
      setDeployingPlatform(null);
    }
  };

  const orbClass =
    agent.role_default === "admin"
      ? "admin"
      : agent.role_default === "guest"
        ? "guest"
        : "member";

  return (
    <div className="dash-card">
      <div className="p-5">
        {/* Agent Header */}
        <div className="flex items-start gap-3 mb-4">
          <div className={`agent-orb ${orbClass}`} />
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
              const platformInfo = PLATFORMS.find(
                (p) => p.key === deployment.platform
              );
              const Icon = platformInfo?.icon;
              return (
                <div
                  key={deployment.platform}
                  className="flex items-center gap-2.5 rounded-xl border border-black/[0.065] bg-[#FAFAF9] px-3 py-2.5"
                >
                  {Icon && (
                    <Icon size={16} color={platformInfo?.color} />
                  )}
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

        {/* Deploy Options — one button per platform */}
        <div className="border-t border-black/[0.065] pt-4">
          <p className="text-[12px] font-medium text-[#6B6B6B] uppercase tracking-wider mb-3">
            Deploy to platform
          </p>
          <div className="grid grid-cols-3 gap-2">
            {PLATFORMS.map((platform) => {
              const Icon = platform.icon;
              const isDeployed = deployedPlatforms.has(platform.key);
              const isExpanded = deployingPlatform === platform.key;
              // For Slack: show as "ready" when bot token is installed via OAuth
              const isSlackReady = platform.key === "slack" && slackConnected && !isDeployed;

              return (
                <button
                  key={platform.key}
                  type="button"
                  onClick={() => {
                    if (isDeployed) return;

                    // Slack OAuth: redirect to install if bot not yet installed,
                    // otherwise deploy directly (bot token is on the server).
                    if (platform.key === "slack" && platform.oauth && !isDeployed) {
                      if (!slackConnected) {
                        window.location.href = buildSlackInstallUrl(collection);
                        return;
                      }
                      // Bot is installed — deploy directly with empty config;
                      // the server looks up the bot token from the OAuth store.
                      setDeployingPlatform(platform.key);
                      setDeployError(null);
                      setDeploySuccess(null);
                      void onDeploy(agent.agent_id, "slack", {});
                      return;
                    }

                    setDeployingPlatform(
                      isExpanded ? null : platform.key
                    );
                    setToken("");
                    setDeployError(null);
                    setDeploySuccess(null);
                  }}
                  disabled={isDeployed}
                  className={`flex flex-col items-center gap-1.5 rounded-xl border p-3 text-[12px] font-medium transition-all duration-200 ${
                    isDeployed
                      ? "border-[#10B981]/20 bg-[#10B981]/[0.03] text-[#10B981] cursor-default"
                      : isExpanded
                        ? "border-[#171717]/20 bg-[#171717]/[0.03] shadow-sm"
                        : isSlackReady
                          ? "border-[#E01E5A]/20 bg-[#E01E5A]/[0.03] text-[#E01E5A]"
                          : "border-black/[0.065] hover:border-black/[0.12] hover:shadow-[0_2px_8px_rgba(0,0,0,0.04)]"
                  }`}
                >
                  <Icon size={20} color={isDeployed ? "#10B981" : platform.color} />
                  <span>{platform.label}</span>
                  {isDeployed && <CheckCircle2 className="h-3.5 w-3.5" />}
                  {isSlackReady && <ExternalLink className="h-3 w-3" />}
                </button>
              );
            })}
          </div>
          {/* Slack: show status message when bot is installed but not yet deployed to this agent */}
          {slackConnected && !deployedPlatforms.has("slack") && (
            <p className="mt-2 text-[11px] text-[#10B981]">
              Slack bot installed — click "Slack" above to deploy this agent.
            </p>
          )}
        </div>

        {/* Deploy Panel — step-by-step instructions + one input (non-OAuth platforms only) */}
        {deployingPlatform && (                    <DeployPanel
            platform={PLATFORMS.find((p) => p.key === deployingPlatform)!}
            token={token}
            setToken={setToken}
            emailConfig={emailConfig}
            setEmailConfig={setEmailConfig}
            loading={deployingPlatform !== null && !deployError && !deploySuccess}
            error={deployError}
            success={deploySuccess}
            onDeploy={() => {
              void handleDeploy(deployingPlatform as "slack" | "github" | "email");
            }}
            onCancel={() => {
              setDeployingPlatform(null);
              setToken("");
              setDeployError(null);
              setDeploySuccess(null);
            }}
          />
        )}
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Deploy Panel — instructions + single input                                  */
/* -------------------------------------------------------------------------- */

function DeployPanel({
  platform,
  token,
  setToken,
  emailConfig,
  setEmailConfig,
  loading,
  error,
  success,
  onDeploy,
  onCancel,
}: {
  platform: (typeof PLATFORMS)[number];
  token: string;
  setToken: (v: string) => void;
  emailConfig?: { from_address: string; smtp_host: string; smtp_port: string; smtp_user: string; smtp_password: string };
  setEmailConfig?: (v: { from_address: string; smtp_host: string; smtp_port: string; smtp_user: string; smtp_password: string }) => void;
  loading: boolean;
  error: string | null;
  success: string | null;
  onDeploy: () => void;
  onCancel: () => void;
}) {
  const isEmail = platform.key === "email";
  return (
    <div className="mt-4 rounded-2xl border border-black/[0.065] bg-[#FAFAF9] p-5 space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-[14px] font-semibold text-[#171717]">
          Connect to {platform.label}
        </p>
        <button
          type="button"
          onClick={onCancel}
          className="text-[12px] text-[#6B6B6B] hover:text-[#171717] transition-colors"
        >
          Close
        </button>
      </div>

      {platform.instruction && !isEmail && (
        <ol className="space-y-1.5">
          {platform.instruction.map((line, i) => (
            <li key={i} className="text-[12px] text-[#6B6B6B] leading-relaxed">
              {line}
            </li>
          ))}
        </ol>
      )}

      {isEmail && emailConfig && setEmailConfig ? (
        <div className="space-y-3">
          <p className="text-[12px] text-[#6B6B6B] leading-relaxed">
            Configure SMTP credentials for this organization's email agent. Each organization stores its own email provider credentials separately.
          </p>
          <div>
            <label className="block mb-1 text-[12px] font-medium text-[#6B6B6B]">From address</label>
            <input
              type="email"
              value={emailConfig.from_address}
              onChange={(e) => setEmailConfig({ ...emailConfig, from_address: e.target.value })}
              placeholder="cortex@yourcompany.com"
              className="w-full rounded-xl border border-black/[0.08] bg-white px-4 py-3 text-[13px] text-[#171717] placeholder:text-[#9A9A9A] outline-none transition-all duration-200 focus:border-[#171717]/20 focus:ring-2 focus:ring-[#171717]/5"
            />
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div className="col-span-2">
              <label className="block mb-1 text-[12px] font-medium text-[#6B6B6B]">SMTP host</label>
              <input
                type="text"
                value={emailConfig.smtp_host}
                onChange={(e) => setEmailConfig({ ...emailConfig, smtp_host: e.target.value })}
                placeholder="smtp.gmail.com"
                className="w-full rounded-xl border border-black/[0.08] bg-white px-4 py-3 text-[13px] text-[#171717] placeholder:text-[#9A9A9A] outline-none transition-all duration-200 focus:border-[#171717]/20 focus:ring-2 focus:ring-[#171717]/5"
              />
            </div>
            <div>
              <label className="block mb-1 text-[12px] font-medium text-[#6B6B6B]">Port</label>
              <input
                type="text"
                value={emailConfig.smtp_port}
                onChange={(e) => setEmailConfig({ ...emailConfig, smtp_port: e.target.value })}
                placeholder="587"
                className="w-full rounded-xl border border-black/[0.08] bg-white px-4 py-3 text-[13px] text-[#171717] placeholder:text-[#9A9A9A] outline-none transition-all duration-200 focus:border-[#171717]/20 focus:ring-2 focus:ring-[#171717]/5"
              />
            </div>
          </div>
          <div>
            <label className="block mb-1 text-[12px] font-medium text-[#6B6B6B]">SMTP username</label>
            <input
              type="text"
              value={emailConfig.smtp_user}
              onChange={(e) => setEmailConfig({ ...emailConfig, smtp_user: e.target.value })}
              placeholder="Usually the email address"
              className="w-full rounded-xl border border-black/[0.08] bg-white px-4 py-3 text-[13px] text-[#171717] placeholder:text-[#9A9A9A] outline-none transition-all duration-200 focus:border-[#171717]/20 focus:ring-2 focus:ring-[#171717]/5"
            />
          </div>
          <div>
            <label className="block mb-1 text-[12px] font-medium text-[#6B6B6B]">SMTP password / app password</label>
            <input
              type="password"
              value={emailConfig.smtp_password}
              onChange={(e) => setEmailConfig({ ...emailConfig, smtp_password: e.target.value })}
              placeholder="••••••••"
              className="w-full rounded-xl border border-black/[0.08] bg-white px-4 py-3 text-[13px] text-[#171717] placeholder:text-[#9A9A9A] outline-none transition-all duration-200 focus:border-[#171717]/20 focus:ring-2 focus:ring-[#171717]/5"
            />
          </div>
        </div>
      ) : (
        <div>
          <label className="block mb-1 text-[12px] font-medium text-[#6B6B6B]">
            {platform.inputLabel ?? "Value"}
          </label>
          <input
            type="text"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            placeholder={platform.inputPlaceholder ?? "Enter value"}
            className="w-full rounded-xl border border-black/[0.08] bg-white px-4 py-3 text-[13px] text-[#171717] placeholder:text-[#9A9A9A] outline-none transition-all duration-200 focus:border-[#171717]/20 focus:ring-2 focus:ring-[#171717]/5"
            autoFocus
          />
        </div>
      )}

      {error && <p className="text-[12px] text-[#EF4444]">{error}</p>}
      {success && <p className="text-[12px] text-[#10B981]">{success}</p>}

      <button
        type="button"
        onClick={onDeploy}
        disabled={(!isEmail && platform.inputLabel !== undefined && !token.trim()) || (isEmail && emailConfig && (!emailConfig.from_address.trim() || !emailConfig.smtp_host.trim())) || loading}
        className={`w-full ${loading ? "btn-green" : "btn-orange"}`}
      >
        {loading ? (
          <>
            <Loader2 className="h-4 w-4 animate-spin" />
            Saving…
          </>
        ) : (
          `Save ${platform.label} configuration`
        )}
      </button>
    </div>
  );
}
