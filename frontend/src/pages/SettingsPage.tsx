import { LogOut, ShieldCheck } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Avatar } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/shared/states";
import { useAuth } from "@/auth/AuthContext";
import { ROLE_LABELS } from "@/lib/nav";
import { cn } from "@/lib/utils";

export function SettingsPage() {
  const { user, role, brains, signOut } = useAuth();
  const name =
    (user?.user_metadata?.full_name as string | undefined)?.trim() ||
    user?.email?.split("@")[0] ||
    "you";

  return (
    <div className="max-w-2xl space-y-6">
      <PageHeader title="Settings" subtitle="Your profile and access" />

      <Card>
        <CardHeader>
          <CardTitle>Profile</CardTitle>
        </CardHeader>
        <CardContent className="flex items-center gap-4">
          <Avatar name={name} className="h-12 w-12 text-sm" />
          <div className="min-w-0">
            <p className="text-[15px] font-semibold text-foreground">{name}</p>
            <p className="truncate text-sm text-muted-foreground">{user?.email}</p>
          </div>
          <Badge variant={role === "admin" ? "accent" : "default"} className="ml-auto">
            <ShieldCheck className="h-3 w-3" />
            {role ? ROLE_LABELS[role] : "…"}
          </Badge>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Brains</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2.5">
          {brains.length === 0 ? (
            <p className="text-sm text-muted-foreground">You don&rsquo;t have access to any brain yet.</p>
          ) : (
            brains.map((brain) => (
              <div
                key={brain.collection_name}
                className="flex items-center justify-between rounded-lg border border-border px-3.5 py-2.5"
              >
                <span className="text-[13.5px] font-medium text-foreground">
                  {brain.collection_name}
                </span>
                <Badge variant="outline" className={cn("capitalize")}>
                  {brain.role}
                </Badge>
              </div>
            ))
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Session</CardTitle>
        </CardHeader>
        <CardContent>
          <Button variant="secondary" className="text-destructive hover:bg-destructive/5" onClick={() => void signOut()}>
            <LogOut /> Sign out
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
