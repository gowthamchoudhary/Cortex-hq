import * as React from "react";
import { cn } from "@/lib/utils";
import { initialsFor } from "@/lib/format";

interface AvatarProps extends React.HTMLAttributes<HTMLDivElement> {
  name: string;
  size?: "sm" | "md";
}

export function Avatar({ name, size = "md", className, ...props }: AvatarProps) {
  return (
    <div
      className={cn(
        "flex shrink-0 items-center justify-center rounded-full bg-muted font-semibold text-muted-foreground",
        size === "md" ? "h-8 w-8 text-xs" : "h-6 w-6 text-[10px]",
        className
      )}
      title={name}
      {...props}
    >
      {initialsFor(name || "?")}
    </div>
  );
}
