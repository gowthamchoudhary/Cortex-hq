import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Building2, Link2, Loader2, Trash2, ArrowRight } from "lucide-react";
import { useAuth } from "@/auth/AuthContext";
import { createBrain, acceptInvitation, deleteBrain } from "@/api/brains";
import { api } from "@/lib/api";

type Tab = "create" | "join";

/** Extract just the token from an invite URL or raw token string. */
function extractInviteToken(input: string): string {
  const trimmed = input.trim();
  // If it looks like a URL, extract the last path segment after /invite/
  try {
    if (trimmed.includes("/invite/")) {
      const parts = trimmed.split("/invite/");
      const after = parts[parts.length - 1];
      // Strip any query params or trailing slashes
      const token = after.split("?")[0].split("/")[0].trim();
      if (token) return token;
    }
  } catch {
    // fall through
  }
  return trimmed;
}

interface BrainInfo {
  collection_name: string;
  role: string;
}

export function OnboardingPage() {
  const navigate = useNavigate();
  const [tab, setTab] = useState<Tab>("create");
  const [brains, setBrains] = useState<BrainInfo[]>([]);
  const [deleting, setDeleting] = useState<string | null>(null);
  const { refreshIdentity } = useAuth();

  useEffect(() => {
    api
      .get<{ ok: boolean; brains?: BrainInfo[] }>("/me")
      .then((res) => {
        if (res.ok && res.brains && res.brains.length > 0) {
          setBrains(res.brains);
        }
      })
      .catch(() => {});
  }, []);

  const handleDeleteBrain = async (collectionName: string) => {
    if (!confirm(`Remove yourself from "${collectionName}"? This won't delete the organization.`)) return;
    setDeleting(collectionName);
    try {
      await deleteBrain(collectionName);
      setBrains((prev) => prev.filter((b) => b.collection_name !== collectionName));
      await refreshIdentity();
    } catch {
      // ignore
    } finally {
      setDeleting(null);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#F5F5F4] px-4">
      <div className="w-full max-w-lg">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-3xl font-semibold tracking-tight text-[#171717] mb-2">
            Welcome to Cortex
          </h1>
          <p className="text-[15px] text-[#6B6B6B]">
            Create a new organization or join an existing one to get started.
          </p>
        </div>

        {/* Existing brains */}
        {brains.length > 0 && (
          <div className="mb-6">
            <p className="text-[13px] font-medium text-[#6B6B6B] mb-3">
              Your organizations
            </p>
            <div className="space-y-2">
              {brains.map((brain) => (
                <div
                  key={brain.collection_name}
                  className="flex items-center justify-between rounded-xl bg-white border border-black/[0.065] px-4 py-3 group"
                >
                  <button
                    type="button"
                    onClick={() => {
                      navigate(`/app?collection=${encodeURIComponent(brain.collection_name)}`);
                    }}
                    className="flex items-center gap-3 flex-1 text-left min-w-0"
                  >
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[#171717] text-white">
                      <Building2 className="h-4 w-4" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-[14px] font-medium text-[#171717] truncate">
                        {brain.collection_name}
                      </p>
                      <p className="text-[12px] text-[#9A9A9A] capitalize">
                        {brain.role}
                      </p>
                    </div>
                    <ArrowRight className="h-4 w-4 text-[#9A9A9A] group-hover:text-[#171717] transition-colors shrink-0" />
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDeleteBrain(brain.collection_name)}
                    disabled={deleting === brain.collection_name}
                    className="ml-2 p-1.5 rounded-lg text-[#9A9A9A] hover:text-[#EF4444] hover:bg-[#EF4444]/10 transition-all disabled:opacity-40 shrink-0"
                    title="Leave organization"
                  >
                    {deleting === brain.collection_name ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <Trash2 className="h-3.5 w-3.5" />
                    )}
                  </button>
                </div>
              ))}
            </div>
            <div className="my-6 border-t border-black/[0.065]" />
          </div>
        )}

        {/* Tab switcher */}
        <div className="flex rounded-xl bg-white border border-black/[0.065] p-1 mb-6">
          <button
            type="button"
            onClick={() => setTab("create")}
            className={`flex-1 flex items-center justify-center gap-2 rounded-lg py-2.5 text-[14px] font-medium transition-all duration-200 ${
              tab === "create"
                ? "bg-[#171717] text-white shadow-sm"
                : "text-[#6B6B6B] hover:text-[#171717] hover:bg-black/[0.03]"
            }`}
          >
            <Building2 className="h-4 w-4" />
            Create organization
          </button>
          <button
            type="button"
            onClick={() => setTab("join")}
            className={`flex-1 flex items-center justify-center gap-2 rounded-lg py-2.5 text-[14px] font-medium transition-all duration-200 ${
              tab === "join"
                ? "bg-[#171717] text-white shadow-sm"
                : "text-[#6B6B6B] hover:text-[#171717] hover:bg-black/[0.03]"
            }`}
          >
            <Link2 className="h-4 w-4" />
            Join organization
          </button>
        </div>

        {/* Cards */}
        {tab === "create" ? (
          <CreateOrgCard
            onComplete={() => {
              refreshIdentity().then(() => navigate("/app"));
            }}
          />
        ) : (
          <JoinOrgCard
            onComplete={() => {
              refreshIdentity().then(() => navigate("/app"));
            }}
          />
        )}
      </div>
    </div>
  );
}

function CreateOrgCard({ onComplete }: { onComplete: () => void }) {
  const { refreshIdentity } = useAuth();
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) return;
    setLoading(true);
    setError(null);
    try {
      await createBrain(trimmed);
      await refreshIdentity();
      onComplete();
    } catch (err: any) {
      setError(err?.message || "Failed to create organization. Please try again.");
      setLoading(false);
    }
  };

  return (
    <div className="rounded-2xl bg-white border border-black/[0.065] shadow-[0_4px_20px_rgba(0,0,0,0.035)] p-8">
      <div className="flex items-center gap-3 mb-6">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#171717] text-white">
          <Building2 className="h-5 w-5" />
        </div>
        <div>
          <h2 className="text-[16px] font-semibold text-[#171717]">Create an organization</h2>
          <p className="text-[13px] text-[#6B6B6B]">Set up a new Cortex brain for your team</p>
        </div>
      </div>

      <form onSubmit={handleSubmit}>
        <label className="block mb-1 text-[13px] font-medium text-[#171717]">
          Organization name
        </label>
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="e.g. Acme Corp"
          className="w-full rounded-xl border border-black/[0.08] bg-[#FAFAF9] px-4 py-3 text-[14px] text-[#171717] placeholder:text-[#9A9A9A] outline-none transition-all duration-200 focus:border-[#171717]/20 focus:ring-2 focus:ring-[#171717]/5"
          autoFocus
          disabled={loading}
        />

        {error && (
          <p className="mt-2 text-[13px] text-[#EF4444]">{error}</p>
        )}

        <button
          type="submit"
          disabled={loading || !name.trim()}
          className="mt-6 w-full flex items-center justify-center gap-2 rounded-xl px-5 py-3 text-[14px] font-medium text-white transition-all duration-200 disabled:opacity-40"
          style={{
            background: "linear-gradient(180deg, #252525 0%, #171717 100%)",
            boxShadow: "0 1px 2px rgba(0,0,0,0.15), inset 0 1px 0 rgba(255,255,255,0.08)",
            border: "1px solid rgba(255,255,255,0.10)",
          }}
        >
          {loading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            "Create organization"
          )}
        </button>
      </form>

      <p className="mt-4 text-[12px] text-[#9A9A9A] text-center">
        You'll be registered as the admin of this organization.
      </p>
    </div>
  );
}

function JoinOrgCard({ onComplete }: { onComplete: () => void }) {
  const { refreshIdentity } = useAuth();
  const [token, setToken] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const raw = token.trim();
    if (!raw) return;
    setLoading(true);
    setError(null);
    setSuccess(null);

    // Extract just the token from a pasted URL
    const extracted = extractInviteToken(raw);

    try {
      const result = await acceptInvitation(extracted);
      if (result.status === "verification_required") {
        setError("Your work email needs to be verified before you can join. Please check your inbox.");
        setLoading(false);
        return;
      }
      setSuccess("Invitation accepted! Redirecting to your dashboard…");
      await refreshIdentity();
      setTimeout(onComplete, 800);
    } catch (err: any) {
      // Surface the backend's specific error message if available
      const msg = err?.message || err?.toString() || "";
      let userMsg = "Invalid or expired invitation link. Please try again.";
      if (msg.includes("already been accepted")) {
        userMsg = "This invitation has already been accepted. Ask your admin to send a new one.";
      } else if (msg.includes("expired")) {
        userMsg = "This invitation has expired. Ask your admin to send a new one.";
      } else if (msg.includes("not been verified")) {
        userMsg = "Your work email has not been verified yet. Please verify your email first.";
      } else if (msg.includes("not found")) {
        userMsg = "Employee record not found. Please ask your admin to re-send the invitation.";
      }
      setError(userMsg);
      setLoading(false);
    }
  };

  return (
    <div className="rounded-2xl bg-white border border-black/[0.065] shadow-[0_4px_20px_rgba(0,0,0,0.035)] p-8">
      <div className="flex items-center gap-3 mb-6">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#171717] text-white">
          <Link2 className="h-5 w-5" />
        </div>
        <div>
          <h2 className="text-[16px] font-semibold text-[#171717]">Join an organization</h2>
          <p className="text-[13px] text-[#6B6B6B]">Paste the invitation link you received</p>
        </div>
      </div>

      <form onSubmit={handleSubmit}>
        <label className="block mb-1 text-[13px] font-medium text-[#171717]">
          Invitation link or token
        </label>
        <input
          type="text"
          value={token}
          onChange={(e) => setToken(e.target.value)}
          placeholder="https://cortex-six-eosin.vercel.app/invite/..."
          className="w-full rounded-xl border border-black/[0.08] bg-[#FAFAF9] px-4 py-3 text-[14px] text-[#171717] placeholder:text-[#9A9A9A] outline-none transition-all duration-200 focus:border-[#171717]/20 focus:ring-2 focus:ring-[#171717]/5"
          autoFocus
          disabled={loading}
        />

        {error && (
          <p className="mt-2 text-[13px] text-[#EF4444]">{error}</p>
        )}
        {success && (
          <p className="mt-2 text-[13px] text-[#10B981]">{success}</p>
        )}

        <button
          type="submit"
          disabled={loading || !token.trim()}
          className="mt-6 w-full flex items-center justify-center gap-2 rounded-xl px-5 py-3 text-[14px] font-medium text-white transition-all duration-200 disabled:opacity-40"
          style={{
            background: "linear-gradient(180deg, #252525 0%, #171717 100%)",
            boxShadow: "0 1px 2px rgba(0,0,0,0.15), inset 0 1px 0 rgba(255,255,255,0.08)",
            border: "1px solid rgba(255,255,255,0.10)",
          }}
        >
          {loading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            "Join organization"
          )}
        </button>
      </form>

      <p className="mt-4 text-[12px] text-[#9A9A9A] text-center">
        Ask your admin to send you an invitation link.
      </p>
    </div>
  );
}
