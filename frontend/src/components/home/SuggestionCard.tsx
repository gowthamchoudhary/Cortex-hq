import { Sparkles } from "lucide-react";
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
      className="group flex flex-col items-start gap-2 rounded-2xl border border-border bg-surface p-4 text-left shadow-card transition-all hover:-translate-y-0.5 hover:shadow-lift"
    >
      <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-accent/10 text-accent">
        <Sparkles className="h-3.5 w-3.5" />
      </div>
      <p className="text-[13.5px] font-medium leading-snug text-foreground">{suggestion.prompt}</p>
      <p className="text-[12px] text-faint">{suggestion.source}</p>
    </button>
  );
}
