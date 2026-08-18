import { useState } from "react";
import { ArrowUp, Loader2, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
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
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <Card className="overflow-hidden">
        <CardContent className="p-0">
          <div className="flex items-end gap-2 p-3">
            <Textarea
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void submit(question);
                }
              }}
              placeholder="Ask Cortex anything…"
              className="min-h-[48px] resize-none border-0 bg-transparent px-3 py-2.5 text-[15px] focus-visible:ring-0"
              rows={1}
            />
            <Button
              size="icon"
              className="h-9 w-9 shrink-0 rounded-lg"
              disabled={loading || !question.trim()}
              onClick={() => void submit(question)}
              aria-label="Ask"
            >
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowUp className="h-4 w-4" />}
            </Button>
          </div>
          <div className="flex items-center gap-3 border-t border-border px-4 py-2 text-[12px] text-faint">
            <span className="inline-flex items-center gap-1.5">
              <ShieldCheck className="h-3.5 w-3.5" />
              Answers respect your role&rsquo;s access level
            </span>
            {collection ? (
              <span className="ml-auto rounded-full border border-border px-2 py-0.5">{collection}</span>
            ) : null}
          </div>
        </CardContent>
      </Card>

      {error ? (
        <p className="mt-3 text-[13px] text-destructive">{error}</p>
      ) : null}

      {result ? (
        <Card className="mt-4">
          <CardContent className="space-y-3 p-5">
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-[13px] font-semibold text-foreground">{result.question}</p>
              {result.abstained ? (
                <Badge variant="warning">Couldn&rsquo;t verify</Badge>
              ) : (
                <Badge variant="success">
                  {Math.round((result.confidence ?? 0) * 100)}% confidence
                </Badge>
              )}
            </div>
            <p className="text-[14.5px] leading-relaxed text-foreground">{result.answer}</p>
            {result.evidence && result.evidence.length > 0 ? (
              <div className="pt-1">
                <p className="mb-1.5 text-[11px] font-medium uppercase tracking-wide text-faint">
                  Evidence · {formatNumber(result.evidence.length)}
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {result.evidence.slice(0, 8).map((doc) => (
                    <code
                      key={doc}
                      className="max-w-[260px] truncate rounded-md border border-border bg-muted px-1.5 py-0.5 text-[11px] text-muted-foreground"
                      title={doc}
                    >
                      {doc}
                    </code>
                  ))}
                </div>
              </div>
            ) : null}
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
