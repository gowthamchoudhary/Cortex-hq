import * as React from "react";
import { NavLink } from "react-router-dom";
import { LogOut, Settings } from "lucide-react";
import { LogoMark } from "@/components/brand/Logo";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Separator } from "@/components/ui/separator";
import { useAuth } from "@/auth/AuthContext";
import { navForRole, ROLE_LABELS } from "@/lib/nav";
import { cn } from "@/lib/utils";
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
    <aside className="flex h-full w-[232px] shrink-0 flex-col border-r border-border bg-surface">
      {/* Logo */}
      <div className="flex h-16 items-center px-5">
        <NavLink to="/app" className="flex items-center gap-2.5">
          <LogoMark />
          <span className="text-[15px] font-semibold tracking-tight">Cortex</span>
        </NavLink>
      </div>

      <Separator />

      {/* Navigation */}
      <nav className="flex-1 space-y-6 overflow-y-auto px-3 py-5">
        <div className="space-y-0.5">
          {main.map((item) => (
            <SidebarLink key={item.to} to={item.to} label={item.label} icon={item.icon} />
          ))}
        </div>

        {admin.length > 0 && (
          <div className="space-y-0.5">
            <p className="px-2 pb-1.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-faint">
              Workspace
            </p>
            {admin.map((item) => (
              <SidebarLink key={item.to} to={item.to} label={item.label} icon={item.icon} />
            ))}
          </div>
        )}
      </nav>

      {/* Bottom: settings + profile */}
      <div className="space-y-0.5 px-3 pb-4">
        {bottom.map((item) => (
          <SidebarLink key={item.to} to={item.to} label={item.label} icon={item.icon} />
        ))}
        <Separator className="my-3" />
        <DropdownMenu>
          <DropdownMenuTrigger className="flex w-full items-center gap-2.5 rounded-lg px-2 py-2 text-left transition-colors hover:bg-muted focus:outline-none focus-visible:ring-2 focus-visible:ring-ring/30">
            <Avatar name={displayName} />
            <div className="min-w-0 flex-1">
              <p className="truncate text-[13px] font-medium leading-tight text-foreground">
                {displayName}
              </p>
              <p className="truncate text-[11px] leading-tight text-faint">{email}</p>
            </div>
            <Badge variant="outline" className="px-1.5 py-0 text-[10px]">
              {ROLE_LABELS[role] ?? role}
            </Badge>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" side="top" className="w-56">
            <DropdownMenuLabel>
              <div className="truncate text-[13px] font-medium text-foreground">{email}</div>
              <div className="text-[11px] font-normal text-faint">{ROLE_LABELS[role] ?? role} workspace</div>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem asChild>
              <NavLink to="/settings">
                <Settings /> Settings
              </NavLink>
            </DropdownMenuItem>
            <DropdownMenuItem
              className="text-destructive focus:text-destructive"
              onClick={() => void signOut()}
            >
              <LogOut /> Sign out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
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
        cn(
          "flex items-center gap-2.5 rounded-lg px-2 py-1.5 text-[13.5px] font-medium transition-colors",
          isActive
            ? "bg-muted text-foreground"
            : "text-muted-foreground hover:bg-muted/60 hover:text-foreground"
        )
      }
    >
      <Icon className="h-4 w-4 shrink-0" />
      {label}
    </NavLink>
  );
}

