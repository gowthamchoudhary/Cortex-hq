import { useState } from "react";
import { ArrowUp, Loader2, ShieldCheck } from "lucide-react";
import { Textarea } from "@/components/ui/textarea";
import { askQuestion } from "@/api/ask";
import { formatNumber } from "@/lib/format";
import type { AskResponse } from "@/types/api";

export function AskBar({
  collection,
  initialQuestion = "",
}: {
  collection?: string;
  initialQuestion?: string;
}) {
  const [question, setQuestion] = useState(initialQuestion);
  const [result, setResult] = useState<AskResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const submit = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || loading) return;
    setError(null);
    setResult(null);
    setLoading(true);
    try {
      setResult(await askQuestion(trimmed, collection));
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Something went wrong."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div className="ask-panel">
        <div className="ask-panel-input-area">
          <Textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                void submit(question);
              }
            }}
            placeholder="Ask a question about your organization's knowledge..."
            className="min-h-[48px] resize-none border-0 bg-transparent px-2 py-2 text-[14.5px] focus-visible:ring-0"
            rows={1}
          />
          <button
            type="button"
            className="dash-btn dash-btn-primary dash-btn-icon"
            style={{ height: 38, width: 38, borderRadius: 10 }}
            disabled={loading || !question.trim()}
            onClick={() => void submit(question)}
            aria-label="Ask"
          >
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <ArrowUp className="h-4 w-4" />
            )}
          </button>
        </div>
        <div className="ask-panel-footer">
          <span className="inline-flex items-center gap-1.5">
            <ShieldCheck className="h-3.5 w-3.5" />
            Answers respect your role's access level
          </span>
          {collection ? (
            <span className="ml-auto source-badge">{collection}</span>
          ) : null}
        </div>
      </div>

      {error ? (
        <p className="mt-3 text-[13px] text-destructive">{error}</p>
      ) : null}

      {result ? (
        <div className="dash-card mt-4">
          <div className="dash-card-body space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-[13.5px] font-semibold text-foreground">
                {result.question}
              </p>
              {result.abstained ? (
                <span
                  className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium"
                  style={{
                    background: "hsl(38 92% 46% / 0.1)",
                    color: "hsl(38 92% 46%)",
                  }}
                >
                  Couldn't verify
                </span>
              ) : (
                <span
                  className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium"
                  style={{
                    background: "hsl(152 60% 36% / 0.1)",
                    color: "hsl(152 60% 36%)",
                  }}
                >
                  {Math.round((result.confidence ?? 0) * 100)}% confidence
                </span>
              )}
            </div>
            <p className="text-[14.5px] leading-relaxed text-foreground">
              {result.answer}
            </p>
            {result.evidence && result.evidence.length > 0 ? (
              <div className="pt-1">
                <p className="mb-1.5 text-[11px] font-medium uppercase tracking-wide text-faint">
                  Evidence · {formatNumber(result.evidence.length)}
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {result.evidence.slice(0, 8).map((doc) => (
                    <code
                      key={doc}
                      className="max-w-[260px] truncate rounded-lg border border-border bg-muted px-2 py-0.5 text-[11px] text-muted-foreground"
                      title={doc}
                    >
                      {doc}
                    </code>
                  ))}
                </div>
              </div>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}
