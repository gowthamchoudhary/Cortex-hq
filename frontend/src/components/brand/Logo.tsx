import { cn } from "@/lib/utils";

export function LogoMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
      className={cn("h-6 w-6", className)}
    >
      <circle cx="12" cy="4" r="1.9" fill="#7EC9FF" />
      <circle cx="4.8" cy="10.2" r="1.9" fill="#7EC9FF" />
      <circle cx="19.2" cy="10.2" r="1.9" fill="#7EC9FF" />
      <circle cx="8.6" cy="18.4" r="1.9" fill="#A5C9F5" />
      <circle cx="15.4" cy="18.4" r="1.9" fill="#A5C9F5" />
      <circle cx="12" cy="11.6" r="1.9" fill="#38BDF8" />
      <path
        d="M12 5.9 L5.6 9.0 M12 5.9 L18.4 9.0 M5.6 9.0 L8.6 16.6 M18.4 9.0 L15.4 16.6 M12 13.5 L8.6 16.6 M12 13.5 L15.4 16.6"
        stroke="#3B82F6"
        strokeWidth="1.1"
        opacity="0.85"
      />
    </svg>
  );
}

export function Logo({ className }: { className?: string }) {
  return (
    <div className={cn("flex items-center gap-2.5", className)}>
      <LogoMark />
      <span className="text-[15px] font-semibold tracking-tight text-foreground">Cortex</span>
    </div>
  );
}
