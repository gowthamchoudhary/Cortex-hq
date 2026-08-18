import * as React from "react";
import { AlertTriangle, Inbox, RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";

export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: string;
  subtitle?: string;
  actions?: React.ReactNode;
}) {
  return (
    <div className="page-header">
      <div>
        <h1 className="page-title">{title}</h1>
        {subtitle ? <p className="page-subtitle">{subtitle}</p> : null}
      </div>
      {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
    </div>
  );
}

export function LoadingState({ rows = 3 }: { rows?: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="dash-card p-5">
          <div className="flex items-start gap-3">
            <div className="h-9 w-9 animate-pulse rounded-xl bg-muted" />
            <div className="flex-1 space-y-2.5">
              <div className="h-4 w-48 animate-pulse rounded-lg bg-muted" />
              <div className="h-3 w-32 animate-pulse rounded bg-muted" />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

export function ErrorState({
  title = "Something went wrong",
  message,
  onRetry,
  className,
}: {
  title?: string;
  message?: string;
  onRetry?: () => void;
  className?: string;
}) {
  return (
    <div className={cn("dash-card", className)}>
      <div className="empty-state">
        <div className="empty-state-icon" style={{ background: "hsl(0 72% 48% / 0.08)" }}>
          <AlertTriangle style={{ color: "hsl(0 72% 48%)" }} />
        </div>
        <div>
          <p className="empty-state-title">{title}</p>
          {message ? (
            <p className="empty-state-message">{message}</p>
          ) : null}
        </div>
        {onRetry ? (
          <button
            type="button"
            onClick={onRetry}
            className="dash-btn dash-btn-secondary"
          >
            <RefreshCw className="h-4 w-4" />
            Try again
          </button>
        ) : null}
      </div>
    </div>
  );
}

export function EmptyState({
  title,
  message,
  action,
  className,
}: {
  title: string;
  message?: string;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("dash-card", className)}>
      <div className="empty-state">
        <div className="empty-state-icon">
          <Inbox />
        </div>
        <div>
          <p className="empty-state-title">{title}</p>
          {message ? (
            <p className="empty-state-message">{message}</p>
          ) : null}
        </div>
        {action}
      </div>
    </div>
  );
}
