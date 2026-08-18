import * as React from "react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { AlertCircle, Lock, Mail, User } from "lucide-react";
import { LogoMark } from "@/components/brand/Logo";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/auth/AuthContext";
import { cn } from "@/lib/utils";

const GOOGLE_G_SVG = (
  <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden="true">
    <path fill="#FFC107" d="M43.6 20.1H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.9 1.2 8 3l5.7-5.7C34.5 6.1 29.5 4 24 4 13 4 4 13 4 24s9 20 20 20 20-9 20-20c0-1.3-.1-2.6-.4-3.9z" />
    <path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.9 1.2 8 3l5.7-5.7C34.5 6.1 29.5 4 24 4 16.3 4 9.7 8.3 6.3 14.7z" />
    <path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-8l-6.5 5C9.5 39.6 16.2 44 24 44z" />
    <path fill="#1976D2" d="M43.6 20.1H42V20H24v8h11.3c-.8 2.3-2.3 4.3-4.1 5.7l6.2 5.2C36.9 40.9 44 36 44 24c0-1.3-.1-2.6-.4-3.9z" />
  </svg>
);

type Mode = "signin" | "signup";

export function AuthPage() {
  const { loading, session, configured } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  // Preserve the intended destination across the Google OAuth round-trip
  // (the callback URL only carries ?code=..., so we stash it first).
  const storedReturn = sessionStorage.getItem("cortex:returnTo");
  const returnTo = searchParams.get("returnTo") || storedReturn || "/";
  const [mode, setMode] = useState<Mode>("signin");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [magicOpen, setMagicOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [magicEmail, setMagicEmail] = useState("");

  const { signInWithPassword, signUp, signInWithOtp, signInWithGoogle } = useAuth();
  const navigateRef = useRef(navigate);
  navigateRef.current = navigate;

  // After Supabase restores a session (normal load, Google OAuth callback,
  // or magic-link callback) send the user into the app.
  useEffect(() => {
    if (!loading && session) {
      sessionStorage.removeItem("cortex:returnTo");
      navigateRef.current(returnTo, { replace: true });
    }
  }, [loading, session, returnTo]);

  const run = useCallback(
    async (fn: () => Promise<void>) => {
      setError(null);
      setNotice(null);
      setSubmitting(true);
      try {
        await fn();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Something went wrong. Please try again.");
      } finally {
        setSubmitting(false);
      }
    },
    []
  );

  if (!loading && session) {
    return <Navigate to={returnTo} replace />;
  }

  const handleSignIn = () =>
    run(async () => {
      if (!email || !password) throw new Error("Enter your email and password.");
      await signInWithPassword(email, password);
    });

  const handleSignUp = () =>
    run(async () => {
      if (!name || !email || !password) throw new Error("Fill in your name, email, and password.");
      const { needsConfirmation } = await signUp(name, email, password);
      if (needsConfirmation) {
        setNotice("Account created — check your email to confirm, then sign in.");
        setMode("signin");
      }
    });

  const handleMagicLink = () =>
    run(async () => {
      if (!magicEmail) throw new Error("Enter the email to send the magic link to.");
      await signInWithOtp(magicEmail);
      setNotice("Magic link sent — check your inbox, then tap the link to sign in.");
    });

  const handleGoogle = () => {
    if (!configured) {
      setError("Google sign-in is unavailable until Supabase is configured.");
      return;
    }
    if (returnTo && returnTo !== "/") sessionStorage.setItem("cortex:returnTo", returnTo);
    void run(async () => {
      await signInWithGoogle();
    });
  };

  const title = mode === "signin" ? "Sign in to Cortex" : "Create your account";
  const subtitle =
    mode === "signin"
      ? "Access your organization's living context layer."
      : "Start bringing your organization's context into one living layer.";

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4 py-10">
      <div className="w-full max-w-[420px]">
        <div className="rounded-[18px] border border-border bg-surface px-9 py-10 shadow-card">
          {/* Logo with dotted-circle accent */}
          <div className="relative mx-auto mb-7 flex h-[72px] w-[72px] items-center justify-center">
            <span className="absolute inset-0 rounded-full border-[1.5px] border-dashed border-accent/35" />
            <span className="absolute inset-[9px] rounded-full border-[1.5px] border-dashed border-accent/15" />
            <LogoMark className="relative z-10 h-[52px] w-[52px]" />
          </div>

          <h1 className="text-center text-[27px] font-semibold leading-tight tracking-tight text-foreground">
            {title}
          </h1>
          <p className="mt-2 text-center text-[14.5px] text-muted-foreground">{subtitle}</p>
          <p className="mt-2 mb-7 text-center font-serif text-[16px] italic text-faint">
            Cortex makes it usable.
          </p>

          {error ? (
            <div className="mb-4 flex items-start gap-2 rounded-lg border border-destructive/20 bg-destructive/5 px-3 py-2.5 text-[13px] text-destructive">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          ) : null}
          {notice ? (
            <div className="mb-4 rounded-lg border border-success/20 bg-success/5 px-3 py-2.5 text-[13px] text-success">
              {notice}
            </div>
          ) : null}

          <form
            className="space-y-3.5"
            onSubmit={(e) => {
              e.preventDefault();
              void (mode === "signin" ? handleSignIn() : handleSignUp());
            }}
          >
            {mode === "signup" ? (
              <Field icon={<User className="h-[17px] w-[17px]" />} label="Full name">
                <Input
                  className="pl-10"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Ada Lovelace"
                  autoComplete="name"
                />
              </Field>
            ) : null}
            <Field icon={<Mail className="h-[17px] w-[17px]" />} label="Email">
              <Input
                className="pl-10"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@company.com"
                type="email"
                autoComplete="email"
              />
            </Field>
            <Field icon={<Lock className="h-[17px] w-[17px]" />} label="Password">
              <Input
                className="pl-10"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={mode === "signin" ? "Password" : "Create a password"}
                type="password"
                autoComplete={mode === "signin" ? "current-password" : "new-password"}
              />
            </Field>
            <Button type="submit" className="h-[50px] w-full" disabled={submitting}>
              {mode === "signin" ? "Sign In" : "Create account"}
            </Button>
          </form>

          {/* Dotted divider */}
          <div className="my-5 flex items-center gap-3.5 text-[12.5px] uppercase tracking-[0.05em] text-faint">
            <span className="h-px flex-1 border-t border-dotted border-border" />
            <span>or continue with</span>
            <span className="h-px flex-1 border-t border-dotted border-border" />
          </div>

          {/* Google */}
          <button
            type="button"
            onClick={handleGoogle}
            disabled={submitting}
            className={cn(
              "flex h-[50px] w-full items-center justify-center gap-3 rounded-lg border border-border bg-surface text-[14.5px] font-medium text-foreground transition-colors hover:bg-muted",
              !configured && "cursor-not-allowed opacity-50 hover:bg-surface"
            )}
          >
            {GOOGLE_G_SVG}
            Continue with Google
          </button>

          {/* Magic link */}
          {mode === "signin" ? (
            <div className="mt-5 text-center text-[13.5px] text-muted-foreground">
              <span>No password? </span>
              <button
                type="button"
                onClick={() => setMagicOpen((open) => !open)}
                className="font-semibold text-foreground underline-offset-4 hover:underline"
              >
                {magicOpen ? "Hide magic link" : "Email me a magic link"}
              </button>
            </div>
          ) : null}

          {magicOpen && mode === "signin" ? (
            <form
              className="mt-3.5 space-y-3"
              onSubmit={(e) => {
                e.preventDefault();
                void handleMagicLink();
              }}
            >
              <Field icon={<Mail className="h-[17px] w-[17px]" />} label="Email">
                <Input
                  className="pl-10"
                  value={magicEmail}
                  onChange={(e) => setMagicEmail(e.target.value)}
                  placeholder="you@company.com"
                  type="email"
                />
              </Field>
              <Button type="submit" variant="secondary" className="h-12 w-full" disabled={submitting}>
                Send magic link
              </Button>
            </form>
          ) : null}

          {/* Footer switch */}
          <div className="mt-7 border-t border-border pt-5 text-center text-sm text-muted-foreground">
            {mode === "signin" ? (
              <>
                Don&rsquo;t have an account?{" "}
                <button
                  type="button"
                  onClick={() => {
                    setError(null);
                    setNotice(null);
                    setMode("signup");
                  }}
                  className="font-semibold text-foreground underline-offset-4 hover:underline"
                >
                  Sign Up
                </button>
              </>
            ) : (
              <>
                Already have an account?{" "}
                <button
                  type="button"
                  onClick={() => {
                    setError(null);
                    setNotice(null);
                    setMode("signin");
                  }}
                  className="font-semibold text-foreground underline-offset-4 hover:underline"
                >
                  Sign In
                </button>
              </>
            )}
          </div>
        </div>

        <p className="mt-6 text-center text-xs text-faint">
          <Link to="/" className="hover:text-muted-foreground">
            ← Back to Cortex
          </Link>
        </p>
      </div>
    </div>
  );
}

function Field({
  icon,
  label,
  children,
}: {
  icon: React.ReactNode;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <Label htmlFor={label} className="sr-only">
        {label}
      </Label>
      <div className="relative">
        <span className="pointer-events-none absolute left-3.5 top-1/2 z-10 flex -translate-y-1/2 text-faint">
          {icon}
        </span>
        {children}
      </div>
    </div>
  );
}
