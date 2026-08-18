import * as React from "react";
import { NavLink } from "react-router-dom";
import { LogOut } from "lucide-react";
import { LogoMark } from "@/components/brand/Logo";
import { useAuth } from "@/auth/AuthContext";
import { navForRole, ROLE_LABELS } from "@/lib/nav";
import { initialsFor } from "@/lib/format";
import type { CortexRole } from "@/types/api";

export function Sidebar({ role }: { role: CortexRole }) {
  const { user, signOut } = useAuth();
  const items = navForRole(role);
  const main = items.filter((i) => i.section === "main" || !i.section);
  const admin = items.filter((i) => i.section === "admin");
  const bottom = items.filter((i) => i.section === "bottom");

  const displayName =
    (user?.user_metadata?.full_name as string | undefined)?.trim() ||
    user?.email?.split("@")[0] ||
    "there";
  const email = user?.email || "";

  return (
    <aside className="app-sidebar">
      <div className="sidebar-inner">
        {/* Logo */}
        <div className="sidebar-header">
          <NavLink to="/app" className="flex items-center gap-2.5">
            <LogoMark className="h-6 w-6" />
            <span className="text-[15px] font-semibold tracking-tight text-foreground">
              Cortex
            </span>
          </NavLink>
        </div>

        {/* Navigation */}
        <nav className="sidebar-nav">
          <div className="sidebar-section">
            {main.map((item) => (
              <SidebarLink
                key={item.to}
                to={item.to}
                label={item.label}
                icon={item.icon}
              />
            ))}
          </div>

          {admin.length > 0 && (
            <div className="sidebar-section">
              <p className="sidebar-section-label">Workspace</p>
              {admin.map((item) => (
                <SidebarLink
                  key={item.to}
                  to={item.to}
                  label={item.label}
                  icon={item.icon}
                />
              ))}
            </div>
          )}
        </nav>

        {/* Bottom: settings + profile */}
        <div className="sidebar-footer">
          {bottom.map((item) => (
            <SidebarLink
              key={item.to}
              to={item.to}
              label={item.label}
              icon={item.icon}
            />
          ))}
          <div className="sidebar-user">
            <div className="sidebar-user-avatar">
              {initialsFor(displayName)}
            </div>
            <div className="sidebar-user-info">
              <p className="sidebar-user-name">{displayName}</p>
              <p className="sidebar-user-email">{email}</p>
            </div>
            <span
              className={`sidebar-role-badge ${
                role === "admin" ? "admin" : ""
              }`}
            >
              {ROLE_LABELS[role] ?? role}
            </span>
          </div>
          <button
            type="button"
            onClick={() => void signOut()}
            className="flex w-full items-center gap-2.5 rounded-lg px-2 py-2 text-[13px] font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          >
            <LogOut className="h-4 w-4" />
            Sign out
          </button>
        </div>
      </div>
    </aside>
  );
}

function SidebarLink({
  to,
  label,
  icon: Icon,
}: {
  to: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}) {
  return (
    <NavLink
      to={to}
      end={to === "/app"}
      className={({ isActive }) =>
        `sidebar-link ${isActive ? "active" : ""}`
      }
    >
      <Icon />
      {label}
    </NavLink>
  );
}
