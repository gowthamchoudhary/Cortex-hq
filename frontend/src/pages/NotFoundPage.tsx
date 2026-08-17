import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";

export function NotFoundPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-background px-6 text-center">
      <p className="text-sm font-medium uppercase tracking-[0.14em] text-faint">404</p>
      <h1 className="text-2xl font-semibold tracking-tight text-foreground">This page doesn&rsquo;t exist</h1>
      <p className="max-w-sm text-sm text-muted-foreground">
        The page you&rsquo;re looking for was moved or never existed.
      </p>
      <Button asChild>
        <Link to="/">Back to Cortex</Link>
      </Button>
    </div>
  );
}
