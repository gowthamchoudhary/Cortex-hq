const API_BASE = "/api";

export class ApiError extends Error {
  status: number;
  code: string;
  constructor(status: number, code: string, message: string) {
    super(message || code || `Request failed (${status})`);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

let accessToken: string | null = null;
let _refreshPromise: Promise<string | null> | null = null;

/** The AuthContext keeps this in sync with the current Supabase session. */
export function setAccessToken(token: string | null) {
  accessToken = token;
}

export function getAccessToken(): string | null {
  return accessToken;
}

export const UNAUTHORIZED_EVENT = "cortex:unauthorized";

/** Callback to attempt a Supabase token refresh. Set by AuthContext. */
let _refreshToken: (() => Promise<string | null>) | null = null;
export function setTokenRefreshFn(fn: () => Promise<string | null>) {
  _refreshToken = fn;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    Accept: "application/json",
    ...(init?.headers as Record<string, string> | undefined),
  };
  if (accessToken) headers["Authorization"] = `Bearer ${accessToken}`;
  if (init?.body && typeof init.body === "string") headers["Content-Type"] = "application/json";

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(0, "network", "Cannot reach the Cortex API. Check that the backend is running.");
  }

  if (response.status === 401) {
    // Attempt a silent token refresh before giving up.
    const newToken = await _attemptTokenRefresh();
    if (newToken && newToken !== accessToken) {
      // Retry the request with the fresh token.
      const retryHeaders: Record<string, string> = {
        ...headers,
        Authorization: `Bearer ${newToken}`,
      };
      try {
        response = await fetch(`${API_BASE}${path}`, { ...init, headers: retryHeaders });
      } catch {
        throw new ApiError(0, "network", "Cannot reach the Cortex API. Check that the backend is running.");
      }
      if (response.status === 401) {
        // Refresh succeeded but the backend still rejects — truly expired.
        window.dispatchEvent(new CustomEvent(UNAUTHORIZED_EVENT));
        throw new ApiError(401, "unauthorized", "Your session expired. Sign in again.");
      }
    } else {
      // No refresh available or refresh failed.
      window.dispatchEvent(new CustomEvent(UNAUTHORIZED_EVENT));
      throw new ApiError(401, "unauthorized", "Your session expired. Sign in again.");
    }
  }

  const contentType = response.headers.get("content-type") || "";
  const body = contentType.includes("application/json") ? await response.json().catch(() => null) : null;

  if (!response.ok) {
    const code = body?.error ?? body?.code ?? "error";
    const message = typeof code === "string" && code ? code : `Request failed (${response.status})`;
    throw new ApiError(response.status, String(code), message);
  }
  return body as T;
}

/**
 * Attempt a silent token refresh via Supabase's getSession (which auto-refreshes
 * if the refresh token is valid). Deduplicates concurrent refresh attempts.
 */
async function _attemptTokenRefresh(): Promise<string | null> {
  if (!_refreshToken) return null;
  if (!_refreshPromise) {
    _refreshPromise = _refreshToken().finally(() => {
      _refreshPromise = null;
    });
  }
  return _refreshPromise;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) }),
};
