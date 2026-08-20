import { useCallback, useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Loader2, CheckCircle2, AlertCircle } from "lucide-react";
import { useAuth } from "@/auth/AuthContext";
import { api } from "@/lib/api";

export function InvitePage() {
  const { token } = useParams<{ token: string }>();
  const navigate = useNavigate();
  const { session, loading: authLoading } = useAuth();
  const [status, setStatus] = useState<"loading" | "success" | "error" | "needs_auth">("loading");
  const [message, setMessage] = useState("");

  const acceptInvite = useCallback(
    async (inviteToken: string) => {
      try {
        const result = await api.post<{ ok: boolean; collection_name?: string; reason?: string }>(
          `/invitations/${inviteToken}/accept`
        );
        if (result.ok) {
          setStatus("success");
          setMessage(
            result.collection_name
              ? `You've been added to ${result.collection_name}. Redirecting to your dashboard…`
              : "You've been added to the organization. Redirecting to your dashboard…"
          );
          setTimeout(() => navigate("/app", { replace: true }), 2500);
        } else {
          setStatus("error");
          setMessage(result.reason || "Failed to accept invitation.");
        }
      } catch (err) {
        setStatus("error");
        if (err instanceof Error && err.message.includes("401")) {
          setStatus("needs_auth");
          setMessage("Please sign in first to accept this invitation.");
        } else {
          setMessage(err instanceof Error ? err.message : "Failed to accept invitation.");
        }
      }
    },
    [navigate]
  );

  useEffect(() => {
    if (authLoading) return;
    if (!token) {
      setStatus("error");
      setMessage("Invalid invitation link — no token provided.");
      return;
    }
    if (!session) {
      // Not logged in — redirect to auth, then come back here after login.
      setStatus("needs_auth");
      setMessage("Sign in to accept this invitation.");
      return;
    }
    void acceptInvite(token);
  }, [token, session, authLoading, acceptInvite]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#0C0C0C] px-4">
      <div className="w-full max-w-sm rounded-2xl bg-[#1A1A1A] border border-white/[0.06] p-8 text-center space-y-5">
        <div className="flex justify-center">
          <div className="h-12 w-12 rounded-full bg-[#EB512F]/10 flex items-center justify-center">
            {status === "loading" && <Loader2 className="h-6 w-6 text-[#EB512F] animate-spin" />}
            {status === "success" && <CheckCircle2 className="h-6 w-6 text-[#10B981]" />}
            {(status === "error" || status === "needs_auth") && (
              <AlertCircle className="h-6 w-6 text-[#F59E0B]" />
            )}
          </div>
        </div>

        <div>
          <h1 className="text-[18px] font-semibold text-white">
            {status === "loading" && "Accepting invitation…"}
            {status === "success" && "Welcome!"}
            {status === "error" && "Invitation error"}
            {status === "needs_auth" && "Sign in required"}
          </h1>
          <p className="mt-2 text-[14px] text-white/50 leading-relaxed">{message}</p>
        </div>

        {status === "needs_auth" && (
          <button
            type="button"
            onClick={() =>
              navigate(`/auth?returnTo=${encodeURIComponent(`/invite/${token}`)}`, { replace: true })
            }
            className="w-full rounded-xl bg-[#EB512F] px-4 py-3 text-[14px] font-medium text-white hover:bg-[#E6411C] transition-colors"
          >
            Sign in to continue
          </button>
        )}

        {status === "error" && (
          <button
            type="button"
            onClick={() => navigate("/", { replace: true })}
            className="w-full rounded-xl bg-white/10 px-4 py-3 text-[14px] font-medium text-white/70 hover:bg-white/15 transition-colors"
          >
            Go to homepage
          </button>
        )}
      </div>
    </div>
  );
}
