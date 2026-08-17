import {
  Activity,
  Bot,
  Cable,
  Home,
  LayoutDashboard,
  Network,
  Settings,
  Users,
  type LucideIcon,
} from "lucide-react";
import type { CortexRole } from "@/types/api";

export interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  roles: CortexRole[];
  section?: "main" | "admin" | "bottom";
}

/** One design system, one navigation model — roles only change the items. */
export const NAV_ITEMS: NavItem[] = [
  { to: "/app", label: "Home", icon: Home, roles: ["admin", "member", "guest"], section: "main" },
  { to: "/app/knowledge", label: "Knowledge", icon: Network, roles: ["admin", "member", "guest"], section: "main" },
  { to: "/app/agents", label: "Agents", icon: Bot, roles: ["admin", "member"], section: "main" },
  { to: "/app/activity", label: "Activity", icon: Activity, roles: ["admin", "member"], section: "main" },
  { to: "/app/overview", label: "Overview", icon: LayoutDashboard, roles: ["admin"], section: "admin" },
  { to: "/app/sources", label: "Sources", icon: Cable, roles: ["admin"], section: "admin" },
  { to: "/app/people", label: "People & Access", icon: Users, roles: ["admin"], section: "admin" },
  { to: "/app/settings", label: "Settings", icon: Settings, roles: ["admin", "member", "guest"], section: "bottom" },
];

export const ROLE_LABELS: Record<CortexRole, string> = {
  admin: "Admin",
  member: "Member",
  guest: "Guest",
};

export function navForRole(role: CortexRole): NavItem[] {
  return NAV_ITEMS.filter((item) => item.roles.includes(role));
}

export const DEFAULT_ROLE: CortexRole = "guest";
