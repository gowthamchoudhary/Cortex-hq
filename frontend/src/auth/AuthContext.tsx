import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { Session, User } from "@supabase/supabase-js";
import { getSupabaseClient, supabaseConfigured } from "@/lib/supabase";
import { setAccessToken, UNAUTHORIZED_EVENT } from "@/lib/api";
import { fetchMe } from "@/api/auth";
import type { BrainGrant, CortexRole } from "@/types/api";

interface AuthContextValue {
  /** True while the initial session is being restored. */
  loading: boolean;
  /** False when VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY are missing. */
  configured: boolean;
  session: Session | null;
  user: User | null;
  /** Role resolved from the backend (auth.user_brains) — authoritative. */
  role: CortexRole | null;
  brains: BrainGrant[];
  refreshIdentity: () => Promise<void>;
  signInWithPassword: (email: string, password: string) => Promise<void>;
  signUp: (name: string, email: string, password: string) => Promise<{ needsConfirmation: boolean }>;
  signInWithOtp: (email: string) => Promise<void>;
  signInWithGoogle: () => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [loading, setLoading] = useState(true);
  const [session, setSession] = useState<Session | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [role, setRole] = useState<CortexRole | null>(null);
  const [brains, setBrains] = useState<BrainGrant[]>([]);

  const refreshIdentity = useCallback(async () => {
    try {
      const me = await fetchMe();
      setRole(me.role);
      setBrains(me.brains);
    } catch {
      // 401s are handled globally (UNAUTHORIZED_EVENT); keep the last known
      // identity otherwise rather than hard-failing the whole app.
    }
  }, []);

  useEffect(() => {
    if (!supabaseConfigured) {
      setLoading(false);
      return;
    }
    const client = getSupabaseClient();
    let active = true;

    client.auth
      .getSession()
      .then(({ data }) => {
        if (!active) return;
        setSession(data.session);
        setUser(data.session?.user ?? null);
        setAccessToken(data.session?.access_token ?? null);
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    const { data: subscription } = client.auth.onAuthStateChange((_event, nextSession) => {
      setSession(nextSession);
      setUser(nextSession?.user ?? null);
      setAccessToken(nextSession?.access_token ?? null);
      if (nextSession) void refreshIdentity();
      else {
        setRole(null);
        setBrains([]);
      }
    });

    return () => {
      active = false;
      subscription.subscription.unsubscribe();
    };
  }, [refreshIdentity]);

  // Any API 401 (expired/invalid token) clears the local session so the app
  // bounces back to the sign-in page.
  useEffect(() => {
    const onUnauthorized = () => {
      const client = supabaseConfigured ? getSupabaseClient() : null;
      client?.auth.signOut().catch(() => undefined);
      setSession(null);
      setUser(null);
      setRole(null);
      setBrains([]);
      setAccessToken(null);
    };
    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
  }, []);

  // Once a session exists, resolve the backend role/brains.
  useEffect(() => {
    if (session) void refreshIdentity();
  }, [session, refreshIdentity]);

  const signInWithPassword = useCallback(async (email: string, password: string) => {
    const client = getSupabaseClient();
    const { error } = await client.auth.signInWithPassword({ email, password });
    if (error) throw new Error(error.message);
  }, []);

  const signUp = useCallback(async (name: string, email: string, password: string) => {
    const client = getSupabaseClient();
    const { data, error } = await client.auth.signUp({
      email,
      password,
      options: name.trim() ? { data: { full_name: name.trim() } } : undefined,
    });
    if (error) throw new Error(error.message);
    return { needsConfirmation: !data.session };
  }, []);

  const signInWithOtp = useCallback(async (email: string) => {
    const client = getSupabaseClient();
    const { error } = await client.auth.signInWithOtp({
      email,
      options: { emailRedirectTo: `${window.location.origin}/auth` },
    });
    if (error) throw new Error(error.message);
  }, []);

  const signInWithGoogle = useCallback(async () => {
    const client = getSupabaseClient();
    const { error } = await client.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: `${window.location.origin}/auth` },
    });
    if (error) throw new Error(error.message);
  }, []);

  const signOut = useCallback(async () => {
    const client = supabaseConfigured ? getSupabaseClient() : null;
    await client?.auth.signOut().catch(() => undefined);
    setSession(null);
    setUser(null);
    setRole(null);
    setBrains([]);
    setAccessToken(null);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      loading,
      configured: supabaseConfigured,
      session,
      user,
      role,
      brains,
      refreshIdentity,
      signInWithPassword,
      signUp,
      signInWithOtp,
      signInWithGoogle,
      signOut,
    }),
    [
      loading,
      session,
      user,
      role,
      brains,
      refreshIdentity,
      signInWithPassword,
      signUp,
      signInWithOtp,
      signInWithGoogle,
      signOut,
    ]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
