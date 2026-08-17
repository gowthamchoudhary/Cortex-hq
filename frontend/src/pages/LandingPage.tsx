import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { LogoMark } from "@/components/brand/Logo";
import { Button } from "@/components/ui/button";

export function LandingPage() {
  return (
    <div className="flex min-h-screen flex-col bg-background">
      <header className="mx-auto flex w-full max-w-5xl items-center justify-between px-6 py-6">
        <div className="flex items-center gap-2.5">
          <LogoMark />
          <span className="text-[15px] font-semibold tracking-tight">Cortex</span>
        </div>
        <nav className="hidden items-center gap-6 text-sm text-muted-foreground sm:flex">
          <a href="#" className="transition-colors hover:text-foreground">Docs</a>
          <a href="#" className="transition-colors hover:text-foreground">GitHub</a>
        </nav>
        <Button variant="secondary" size="sm" asChild>
          <Link to="/auth">Sign in</Link>
        </Button>
      </header>

      <main className="flex flex-1 flex-col items-center justify-center px-6 py-16 text-center">
        <p className="mb-5 text-[13px] font-medium uppercase tracking-[0.14em] text-faint">
          The living context layer for your organization
        </p>
        <h1 className="max-w-3xl text-balance text-5xl font-semibold leading-[0.95] tracking-tight text-foreground md:text-6xl">
          Understand your organization.
        </h1>
        <p className="mt-6 max-w-xl text-balance text-[17px] leading-relaxed text-muted-foreground">
          Connect your scattered conversations, documents, code, issues, and decisions into a living
          context layer that your team and agents can use — anywhere, anytime.
        </p>
        <div className="mt-10 flex items-center gap-3">
          <Button size="lg" asChild>
            <Link to="/auth">
              Explore Cortex <ArrowRight />
            </Link>
          </Button>
        </div>
        <p className="mt-12 font-serif text-[17px] italic text-faint">
          Cortex makes it usable.
        </p>
      </main>

      <footer className="mx-auto w-full max-w-5xl px-6 py-6 text-center text-xs text-faint">
        © {new Date().getFullYear()} Cortex
      </footer>
    </div>
  );
}
