import * as React from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "@/auth/AuthContext";
import { Skeleton } from "@/components/ui/skeleton";
import type { CortexRole } from "@/types/api";

const ROLE_RANK: Record<CortexRole, number> = { guest: 0, member: 1, admin: 2 };

export function RequireRole({
  minRole,
  children,
}: {
  minRole: CortexRole;
  children: React.ReactNode;
}) {
  const { role } = useAuth();
  if (role === null) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-56" />
        <Skeleton className="h-40 w-full rounded-2xl" />
      </div>
    );
  }
  if (ROLE_RANK[role] < ROLE_RANK[minRole]) {
    return <Navigate to="/app" replace />;
  }
  return <>{children}</>;
}
