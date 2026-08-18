import { Sparkles, ArrowRight } from "lucide-react";
import type { Suggestion } from "@/types/api";

export function SuggestionCard({
  suggestion,
  onAsk,
}: {
  suggestion: Suggestion;
  onAsk: (prompt: string) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onAsk(suggestion.prompt)}
      className="dash-card dash-card-hover group flex flex-col items-start gap-3 p-5 text-left w-full"
    >
      <div
        className="flex h-8 w-8 items-center justify-center rounded-xl"
        style={{ background: "hsl(var(--accent) / 0.08)" }}
      >
        <Sparkles
          className="h-4 w-4"
          style={{ color: "hsl(var(--accent))" }}
        />
      </div>
      <p className="text-[13.5px] font-medium leading-snug text-foreground">
        {suggestion.prompt}
      </p>
      <div className="flex items-center gap-1.5 text-[12px] text-faint">
        <span>{suggestion.source}</span>
        <ArrowRight className="h-3 w-3 opacity-0 transition-all group-hover:translate-x-0.5 group-hover:opacity-100" />
      </div>
    </button>
  );
}
