import { useCallback, useEffect, useState } from "react";
import { Mail, Building2, UserPlus, Copy, Check, Link2, Loader2 } from "lucide-react";
import { fetchPeople } from "@/api/people";
import { registerEmployee, createInvitation } from "@/api/people";
import { PageHeader, EmptyState, ErrorState, LoadingState } from "@/components/shared/states";
import { useAuth } from "@/auth/AuthContext";
import { formatNumber, initialsFor } from "@/lib/format";
import type { Person } from "@/types/api";

export function PeoplePage() {
  const { selectedBrain, selectedRole } = useAuth();
  const collection = selectedBrain;
  const [items, setItems] = useState<Person[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Invite form state
  const [showInvite, setShowInvite] = useState(false);
  const [inviteName, setInviteName] = useState("");
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteEmployeeId, setInviteEmployeeId] = useState("");
  const [inviteRole, setInviteRole] = useState("member");
  const [inviteLoading, setInviteLoading] = useState(false);
  const [inviteResult, setInviteResult] = useState<{
    ok: boolean;
    message: string;
    inviteUrl?: string;
  } | null>(null);
  const [copied, setCopied] = useState(false);

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

  const handleInvite = async () => {
    if (!inviteName.trim() || !inviteEmail.trim()) return;
    setInviteLoading(true);
    setInviteResult(null);
    try {
      // Step 1: Register employee
      await registerEmployee(collection, {
        name: inviteName.trim(),
        work_email: inviteEmail.trim(),
        employee_id: inviteEmployeeId.trim() || undefined,
        cortex_role: inviteRole,
      });

      const empId =
        inviteEmployeeId.trim() ||
        inviteEmail
          .trim()
          .split("@")[0]
          .replace(/[.+]/g, "-");

      // Step 2: Create invitation
      const invResult = await createInvitation(collection, empId);

      const baseUrl = window.location.origin;
      const inviteUrl = invResult.invite_url || `${baseUrl}/auth?returnTo=/onboarding&invite=${invResult.token || empId}`;

      setInviteResult({
        ok: true,
        message: `Invitation created for ${inviteName.trim()}`,
        inviteUrl,
      });

      // Reset form
      setInviteName("");
      setInviteEmail("");
      setInviteEmployeeId("");
      setInviteRole("member");

      // Reload people list
      await load();
    } catch (err) {
      setInviteResult({
        ok: false,
        message: err instanceof Error ? err.message : "Failed to create invitation.",
      });
    } finally {
      setInviteLoading(false);
    }
  };

  const copyInviteLink = async (url: string) => {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback
      const input = document.createElement("input");
      input.value = url;
      document.body.appendChild(input);
      input.select();
      document.execCommand("copy");
      document.body.removeChild(input);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const isAdmin = selectedRole === "admin";

  if (loading) return <LoadingState rows={6} />;
  if (error) return <ErrorState message={error} onRetry={() => void load()} />;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <PageHeader
          title="People & Access"
          subtitle={
            items.length > 0
              ? `${formatNumber(items.length)} people in the directory`
              : "Directory and access mapping"
          }
        />
        {isAdmin && (
          <button
            type="button"
            onClick={() => setShowInvite(!showInvite)}
            className="btn-orange"
          >
            <UserPlus className="h-4 w-4" />
            Invite people
          </button>
        )}
      </div>

      {/* Invite Form */}
      {showInvite && isAdmin && (
        <div className="dash-card p-6 space-y-5">
          <div className="flex items-center gap-2">
            <UserPlus className="h-4 w-4 text-[#EB512F]" />
            <p className="text-[15px] font-semibold text-[#171717]">Invite a team member</p>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="block text-[12px] font-medium text-[#6B6B6B] mb-1.5">
                Full name *
              </label>
              <input
                type="text"
                value={inviteName}
                onChange={(e) => setInviteName(e.target.value)}
                placeholder="Jane Smith"
                className="w-full rounded-xl border border-black/[0.08] bg-[#FAFAF9] px-3.5 py-2.5 text-[13px] text-[#171717] placeholder:text-[#9A9A9A] outline-none transition-all duration-200 focus:border-[#EB512F]/30 focus:ring-2 focus:ring-[#EB512F]/10"
              />
            </div>
            <div>
              <label className="block text-[12px] font-medium text-[#6B6B6B] mb-1.5">
                Work email *
              </label>
              <input
                type="email"
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
                placeholder="jane@company.com"
                className="w-full rounded-xl border border-black/[0.08] bg-[#FAFAF9] px-3.5 py-2.5 text-[13px] text-[#171717] placeholder:text-[#9A9A9A] outline-none transition-all duration-200 focus:border-[#EB512F]/30 focus:ring-2 focus:ring-[#EB512F]/10"
              />
            </div>
            <div>
              <label className="block text-[12px] font-medium text-[#6B6B6B] mb-1.5">
                Employee ID (optional)
              </label>
              <input
                type="text"
                value={inviteEmployeeId}
                onChange={(e) => setInviteEmployeeId(e.target.value)}
                placeholder="Auto-generated from email if empty"
                className="w-full rounded-xl border border-black/[0.08] bg-[#FAFAF9] px-3.5 py-2.5 text-[13px] text-[#171717] placeholder:text-[#9A9A9A] outline-none transition-all duration-200 focus:border-[#EB512F]/30 focus:ring-2 focus:ring-[#EB512F]/10"
              />
            </div>
            <div>
              <label className="block text-[12px] font-medium text-[#6B6B6B] mb-1.5">
                Cortex role
              </label>
              <select
                value={inviteRole}
                onChange={(e) => setInviteRole(e.target.value)}
                className="w-full rounded-xl border border-black/[0.08] bg-[#FAFAF9] px-3.5 py-2.5 text-[13px] text-[#171717] outline-none transition-all duration-200 focus:border-[#EB512F]/30 focus:ring-2 focus:ring-[#EB512F]/10"
              >
                <option value="member">Member — can access knowledge and ask Cortex</option>
                <option value="admin">Admin — full access including management</option>
                <option value="guest">Guest — read-only access</option>
              </select>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => void handleInvite()}
              disabled={inviteLoading || !inviteName.trim() || !inviteEmail.trim()}
              className="btn-orange"
            >
              {inviteLoading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Creating…
                </>
              ) : (
                "Send invitation"
              )}
            </button>
            <button
              type="button"
              onClick={() => {
                setShowInvite(false);
                setInviteResult(null);
              }}
              className="text-[13px] text-[#6B6B6B] hover:text-[#171717] transition-colors"
            >
              Cancel
            </button>
          </div>

          {/* Invite Result */}
          {inviteResult && (
            <div
              className={`rounded-xl border p-4 ${
                inviteResult.ok
                  ? "border-[#10B981]/20 bg-[#10B981]/5"
                  : "border-[#EF4444]/20 bg-[#EF4444]/5"
              }`}
            >
              <p className="text-[13px] text-[#171717] mb-1">{inviteResult.message}</p>
              {inviteResult.inviteUrl && (
                <div className="mt-3 flex items-center gap-2 rounded-lg bg-white border border-black/[0.06] p-3">
                  <Link2 className="h-4 w-4 shrink-0 text-[#6B6B6B]" />
                  <code className="flex-1 text-[12px] text-[#171717] break-all font-mono">
                    {inviteResult.inviteUrl}
                  </code>
                  <button
                    type="button"
                    onClick={() => void copyInviteLink(inviteResult.inviteUrl!)}
                    className="shrink-0 flex items-center gap-1.5 rounded-lg bg-[#F5F3F0] px-3 py-1.5 text-[12px] font-medium text-[#171717] hover:bg-[#EBEBEA] transition-colors"
                  >
                    {copied ? (
                      <>
                        <Check className="h-3.5 w-3.5 text-[#10B981]" />
                        Copied
                      </>
                    ) : (
                      <>
                        <Copy className="h-3.5 w-3.5" />
                        Copy
                      </>
                    )}
                  </button>
                </div>
              )}
              <p className="text-[11px] text-[#6B6B6B] mt-2">
                Share this link with the person via Slack DM, email, or any messaging app.
                There is no automatic email sending yet.
              </p>
            </div>
          )}
        </div>
      )}

      {/* People List */}
      {items.length === 0 ? (
        <EmptyState
          title="No employees registered"
          message={
            isAdmin
              ? "Invite your first team member to get started. They'll be able to access organizational knowledge based on their Cortex role."
              : "People appear here once the employee directory is populated. Their Cortex role determines what knowledge each person can see."
          }
        />
      ) : (
        <div className="dash-card overflow-hidden">
          {items.map((person) => (
            <div key={person.employee_id} className="list-item">
              <div
                className="list-item-icon"
                style={{
                  background:
                    person.cortex_role === "admin"
                      ? "rgba(124,58,237,0.08)"
                      : person.cortex_role === "guest"
                      ? "rgba(13,148,136,0.08)"
                      : "rgba(37,99,235,0.08)",
                  color:
                    person.cortex_role === "admin"
                      ? "#7C3AED"
                      : person.cortex_role === "guest"
                      ? "#0D9488"
                      : "#2563EB",
                }}
              >
                {initialsFor(person.name)}
              </div>
              <div className="list-item-content">
                <p className="list-item-title">{person.name}</p>
                <div className="list-item-meta">
                  <span className="flex items-center gap-1">
                    <Mail className="h-3 w-3" />
                    {person.work_email}
                  </span>
                  {person.employee_id && (
                    <span className="flex items-center gap-1">
                      <Building2 className="h-3 w-3" />
                      {person.employee_id}
                    </span>
                  )}
                </div>
              </div>
              <span
                className="inline-flex items-center rounded-lg px-2.5 py-1 text-[11px] font-medium"
                style={{
                  background:
                    person.cortex_role === "admin"
                      ? "rgba(124,58,237,0.08)"
                      : person.cortex_role === "guest"
                      ? "rgba(13,148,136,0.08)"
                      : "rgba(37,99,235,0.08)",
                  color:
                    person.cortex_role === "admin"
                      ? "#7C3AED"
                      : person.cortex_role === "guest"
                      ? "#0D9488"
                      : "#2563EB",
                }}
              >
                {person.cortex_role}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
