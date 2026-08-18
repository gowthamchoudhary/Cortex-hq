import { Navigate, Outlet, useLocation } from "react-router-dom";
import { Sidebar } from "@/components/layout/Sidebar";
import { useAuth } from "@/auth/AuthContext";
import type { CortexRole } from "@/types/api";

const ROLE_RANK: Record<CortexRole, number> = { guest: 0, member: 1, admin: 2 };

export function AppShell({ minRole = "guest" }: { minRole?: CortexRole }) {
  const { loading, user, session, role } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="app-shell">
        <div className="app-sidebar">
          <div className="sidebar-inner">
            <div className="sidebar-header">
              <div className="h-6 w-24 animate-pulse rounded bg-muted" />
            </div>
            <div className="sidebar-nav">
              <div className="space-y-3 px-3 py-4">
                <div className="h-4 w-28 animate-pulse rounded bg-muted" />
                <div className="h-4 w-20 animate-pulse rounded bg-muted" />
                <div className="h-4 w-24 animate-pulse rounded bg-muted" />
              </div>
            </div>
          </div>
        </div>
        <div className="app-main">
          <div className="app-content">
            <div className="h-8 w-64 animate-pulse rounded-xl bg-muted" />
            <div className="mt-3 h-4 w-80 animate-pulse rounded bg-muted" />
            <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <div className="h-36 animate-pulse rounded-2xl bg-muted" />
              <div className="h-36 animate-pulse rounded-2xl bg-muted" />
              <div className="h-36 animate-pulse rounded-2xl bg-muted" />
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (!session || !user) {
    const returnTo = location.pathname + location.search;
    return <Navigate to={`/auth?returnTo=${encodeURIComponent(returnTo)}`} replace />;
  }

  const effectiveRole = role ?? "member";
  if (ROLE_RANK[effectiveRole] < ROLE_RANK[minRole]) {
    return <Navigate to="/" replace />;
  }

  return (
    <div className="app-shell">
      <Sidebar role={effectiveRole} />
      <main className="app-main">
        <div className="app-content">
          <Outlet context={{ role: effectiveRole }} />
        </div>
      </main>
    </div>
  );
}
