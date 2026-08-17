import { motion } from "framer-motion";
import { Navigate, Outlet, useLocation } from "react-router-dom";
import { Sidebar } from "@/components/layout/Sidebar";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/auth/AuthContext";
import type { CortexRole } from "@/types/api";

const ROLE_RANK: Record<CortexRole, number> = { guest: 0, member: 1, admin: 2 };

export function AppShell({ minRole = "guest" }: { minRole?: CortexRole }) {
  const { loading, user, session, role } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="flex h-screen">
        <div className="w-[232px] shrink-0 border-r border-border bg-surface p-5">
          <Skeleton className="h-6 w-24" />
          <div className="mt-8 space-y-3">
            <Skeleton className="h-4 w-32" />
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-4 w-28" />
          </div>
        </div>
        <div className="flex-1 p-8">
          <Skeleton className="h-8 w-64" />
          <Skeleton className="mt-3 h-4 w-80" />
          <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <Skeleton className="h-32 rounded-2xl" />
            <Skeleton className="h-32 rounded-2xl" />
            <Skeleton className="h-32 rounded-2xl" />
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
    <div className="flex h-screen overflow-hidden bg-background">
      <Sidebar role={effectiveRole} />
      <main className="flex-1 overflow-y-auto">
        <motion.div
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.22, ease: "easeOut" }}
          className="mx-auto max-w-content px-8 py-8 lg:px-10"
        >
          <Outlet context={{ role: effectiveRole }} />
        </motion.div>
      </main>
    </div>
  );
}
