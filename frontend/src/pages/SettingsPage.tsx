import { LogOut, ShieldCheck } from "lucide-react";
import { PageHeader } from "@/components/shared/states";
import { useAuth } from "@/auth/AuthContext";
import { ROLE_LABELS } from "@/lib/nav";
import { initialsFor } from "@/lib/format";

export function SettingsPage() {
  const { user, role, brains, signOut } = useAuth();
  const name =
    (user?.user_metadata?.full_name as string | undefined)?.trim() ||
    user?.email?.split("@")[0] ||
    "you";

  return (
    <div className="max-w-2xl space-y-6">
      <PageHeader title="Settings" subtitle="Your profile and access" />

      {/* Profile */}
      <div className="dash-card">
        <div className="dash-card-header">
          <p className="dash-card-title">Profile</p>
        </div>
        <div className="dash-card-body flex items-center gap-4">
          <div
            className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl text-sm font-bold"
            style={{
              background:
                "linear-gradient(135deg, hsl(var(--accent) / 0.12), hsl(var(--accent) / 0.06))",
              color: "hsl(var(--accent))",
            }}
          >
            {initialsFor(name)}
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-[15px] font-semibold text-foreground">{name}</p>
            <p className="truncate text-sm text-muted-foreground">
              {user?.email}
            </p>
          </div>
          <span
            className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-[12px] font-medium"
            style={{
              background:
                role === "admin"
                  ? "hsl(var(--accent) / 0.1)"
                  : "hsl(var(--muted))",
              color:
                role === "admin"
                  ? "hsl(var(--accent))"
                  : "hsl(var(--muted-foreground))",
            }}
          >
            <ShieldCheck className="h-3.5 w-3.5" />
            {role ? ROLE_LABELS[role] : "…"}
          </span>
        </div>
      </div>

      {/* Brains */}
      <div className="dash-card">
        <div className="dash-card-header">
          <p className="dash-card-title">Brains</p>
        </div>
        <div className="dash-card-body space-y-2.5">
          {brains.length === 0 ? (
            <p className="text-[13.5px] text-muted-foreground">
              You don't have access to any brain yet.
            </p>
          ) : (
            brains.map((brain) => (
              <div
                key={brain.collection_name}
                className="flex items-center justify-between rounded-xl border border-border px-4 py-3"
              >
                <span className="text-[13.5px] font-medium text-foreground">
                  {brain.collection_name}
                </span>
                <span
                  className="inline-flex items-center rounded-lg px-2 py-0.5 text-[11px] font-medium capitalize"
                  style={{
                    background: "hsl(var(--muted))",
                    color: "hsl(var(--muted-foreground))",
                  }}
                >
                  {brain.role}
                </span>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Session */}
      <div className="dash-card">
        <div className="dash-card-header">
          <p className="dash-card-title">Session</p>
        </div>
        <div className="dash-card-body">
          <button
            type="button"
            onClick={() => void signOut()}
            className="dash-btn dash-btn-secondary text-destructive hover:bg-destructive/5"
          >
            <LogOut className="h-4 w-4" />
            Sign out
          </button>
        </div>
      </div>
    </div>
  );
}
