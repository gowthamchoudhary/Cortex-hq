import * as React from "react";
import { NavLink } from "react-router-dom";
import { LogOut, ChevronDown, Building2 } from "lucide-react";
import { LogoMark } from "@/components/brand/Logo";
import { useAuth } from "@/auth/AuthContext";
import { navForRole, ROLE_LABELS } from "@/lib/nav";
import { initialsFor } from "@/lib/format";
import type { CortexRole } from "@/types/api";

export function Sidebar({ role }: { role: CortexRole }) {
  const { user, signOut, brains, selectedBrain, setSelectedBrain } = useAuth();
  const items = navForRole(role);
  const main = items.filter((i) => i.section === "main" || !i.section);
  const admin = items.filter((i) => i.section === "admin");
  const bottom = items.filter((i) => i.section === "bottom");

  const displayName =
    (user?.user_metadata?.full_name as string | undefined)?.trim() ||
    user?.email?.split("@")[0] ||
    "there";
  const email = user?.email || "";

  const [brainOpen, setBrainOpen] = React.useState(false);

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

        {/* Brain Switcher */}
        {brains.length > 1 && selectedBrain && (
          <div className="px-3 mb-2">
            <div className="relative">
              <button
                type="button"
                onClick={() => setBrainOpen(!brainOpen)}
                className="flex w-full items-center gap-2 rounded-xl border border-black/[0.065] bg-white px-3 py-2 text-left text-[13px] font-medium text-[#171717] shadow-[0_2px_8px_rgba(0,0,0,0.04)] transition-all duration-200 hover:shadow-[0_2px_12px_rgba(0,0,0,0.06)]"
              >
                <Building2 className="h-3.5 w-3.5 text-[#6B6B6B] shrink-0" />
                <span className="truncate flex-1">{selectedBrain}</span>
                <ChevronDown
                  className={`h-3.5 w-3.5 text-[#9A9A9A] transition-transform duration-200 ${
                    brainOpen ? "rotate-180" : ""
                  }`}
                />
              </button>

              {brainOpen && (
                <div className="absolute left-0 right-0 top-full z-50 mt-1 rounded-xl border border-black/[0.065] bg-white py-1 shadow-[0_8px_24px_rgba(0,0,0,0.08)]">
                  {brains.map((brain) => (
                    <button
                      key={brain.collection_name}
                      type="button"
                      onClick={() => {
                        setSelectedBrain(brain.collection_name);
                        setBrainOpen(false);
                      }}
                      className={`flex w-full items-center gap-2 px-3 py-2 text-left text-[13px] transition-colors duration-150 ${
                        brain.collection_name === selectedBrain
                          ? "bg-black/[0.04] font-medium text-[#171717]"
                          : "text-[#6B6B6B] hover:bg-black/[0.02] hover:text-[#171717]"
                      }`}
                    >
                      <Building2 className="h-3.5 w-3.5 shrink-0" />
                      <span className="truncate">{brain.collection_name}</span>
                      <span className="ml-auto text-[11px] text-[#9A9A9A] capitalize">
                        {brain.role}
                      </span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Single brain indicator */}
        {brains.length === 1 && (
          <div className="px-3 mb-2">
            <div className="flex items-center gap-2 rounded-xl bg-white border border-black/[0.04] px-3 py-2 text-[12px] text-[#6B6B6B]">
              <Building2 className="h-3.5 w-3.5 shrink-0" />
              <span className="truncate">{selectedBrain}</span>
            </div>
          </div>
        )}

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
