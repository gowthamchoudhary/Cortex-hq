import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Building2, Link2, Loader2 } from "lucide-react";
import { useAuth } from "@/auth/AuthContext";
import { createBrain, acceptInvitation } from "@/api/brains";

type Tab = "create" | "join";

export function OnboardingPage() {
  const navigate = useNavigate();
  const [tab, setTab] = useState<Tab>("create");

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
          <CreateOrgCard onComplete={() => navigate("/app")} />
        ) : (
          <JoinOrgCard onComplete={() => navigate("/app")} />
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
    const trimmed = token.trim();
    if (!trimmed) return;
    setLoading(true);
    setError(null);
    setSuccess(null);
    try {
      const result = await acceptInvitation(trimmed);
      if (result.status === "verification_required") {
        setError("Your work email needs to be verified before you can join. Please check your inbox.");
        setLoading(false);
        return;
      }
      setSuccess("Invitation accepted! Redirecting to your dashboard…");
      await refreshIdentity();
      setTimeout(onComplete, 800);
    } catch (err: any) {
      setError(err?.message || "Invalid or expired invitation link. Please try again.");
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
          <p className="text-[13px] text-[#6B6B6B]">Enter the invitation link you received</p>
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
          placeholder="Paste your invitation link here"
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
