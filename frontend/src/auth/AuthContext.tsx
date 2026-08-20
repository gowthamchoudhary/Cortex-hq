import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import type { Session, User } from "@supabase/supabase-js";
import { getSupabaseClient, supabaseConfigured } from "@/lib/supabase";
import { setAccessToken, setTokenRefreshFn, UNAUTHORIZED_EVENT } from "@/lib/api";
import { fetchMe } from "@/api/auth";
import type { BrainGrant, CortexRole } from "@/types/api"

interface AuthContextValue {
  /** True while the initial session is being restored. */
  loading: boolean;
  /** False when VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY are missing. */
  configured: boolean;
  session: Session | null;
  user: User | null;
  /** True once the first /api/me call has succeeded (or failed). */
  identityLoaded: boolean;
  /** Role resolved from the backend (auth.user_brains) — authoritative. */
  role: CortexRole | null;
  brains: BrainGrant[];
  /** The currently selected brain collection name. */
  selectedBrain: string | undefined;
  /** The role in the currently selected brain. */
  selectedRole: CortexRole;
  /** Set the selected brain (by collection name). */
  setSelectedBrain: (collectionName: string) => void;
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
  const [selectedBrain, setSelectedBrainState] = useState<string | undefined>(undefined);
  const [identityLoaded, setIdentityLoaded] = useState(false);
  const refreshIdentityIdRef = useRef(0);

  const refreshIdentity = useCallback(async () => {
    const id = ++refreshIdentityIdRef.current;
    try {
      const me = await fetchMe();
      // Ignore stale calls if a newer one has started.
      if (id !== refreshIdentityIdRef.current) return;
      setRole(me.role);
      setBrains(me.brains);
      setIdentityLoaded(true);

      // Auto-select the first brain if none selected yet, or if the
      // previously selected brain no longer exists.
      if (me.brains.length > 0) {
        setSelectedBrainState((prev) => {
          if (prev && me.brains.some((b) => b.collection_name === prev)) {
            return prev;
          }
          return me.brains[0].collection_name;
        });
      } else {
        setSelectedBrainState(undefined);
      }
    } catch {
      if (id !== refreshIdentityIdRef.current) return;
      // Mark identity as loaded even on failure — prevents infinite
      // "checking session" spinner. Keep last known role/brains if any.
      setIdentityLoaded(true);
    }
  }, []);

  // Persist selected brain in sessionStorage so it survives refreshes.
  const setSelectedBrain = useCallback((collectionName: string) => {
    setSelectedBrainState(collectionName);
    try {
      sessionStorage.setItem("cortex:selectedBrain", collectionName);
    } catch {
      // sessionStorage may be unavailable.
    }
  }, []);

  // Restore selected brain from sessionStorage on mount.
  useEffect(() => {
    try {
      const stored = sessionStorage.getItem("cortex:selectedBrain");
      if (stored) setSelectedBrainState(stored);
    } catch {
      // sessionStorage may be unavailable.
    }
  }, []);

  // Register the token refresh function so api.ts can attempt silent refresh on 401.
  useEffect(() => {
    setTokenRefreshFn(async () => {
      const client = supabaseConfigured ? getSupabaseClient() : null;
      if (!client) return null;
      const { data } = await client.auth.getSession();
      const token = data.session?.access_token ?? null;
      setAccessToken(token);
      setSession(data.session);
      setUser(data.session?.user ?? null);
      return token;
    });
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
        setSelectedBrainState(undefined);
        setIdentityLoaded(true);
      }
    });

    return () => {
      active = false;
      subscription.subscription.unsubscribe();
    };
  }, [refreshIdentity]);

  // API 401 that survived the token refresh attempt in api.ts means the
  // session is genuinely dead. Only then do we sign out.
  useEffect(() => {
    const onUnauthorized = () => {
      const client = supabaseConfigured ? getSupabaseClient() : null;
      client?.auth.signOut().catch(() => undefined);
      setSession(null);
      setUser(null);
      setRole(null);
      setBrains([]);
      setSelectedBrainState(undefined);
      setAccessToken(null);
      setIdentityLoaded(true);
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
    setSelectedBrainState(undefined);
    setAccessToken(null);
    try {
      sessionStorage.removeItem("cortex:selectedBrain");
    } catch {
      // ignore
    }
  }, []);

  // Derive the role for the selected brain.
  const selectedRole: CortexRole = useMemo(() => {
    if (!selectedBrain || brains.length === 0) return role ?? "member";
    const match = brains.find((b) => b.collection_name === selectedBrain);
    return match ? match.role : brains[0]?.role ?? role ?? "member";
  }, [selectedBrain, brains, role]);

  const value = useMemo<AuthContextValue>(
    () => ({
      loading,
      configured: supabaseConfigured,
      session,
      user,
      identityLoaded,
      role,
      brains,
      selectedBrain,
      selectedRole,
      setSelectedBrain,
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
      identityLoaded,
      role,
      brains,
      selectedBrain,
      selectedRole,
      setSelectedBrain,
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
