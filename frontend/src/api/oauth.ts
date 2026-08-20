import { api } from "@/lib/api";

export type OAuthProvider = "gmail" | "slack" | "github";

export interface OAuthStatusResponse {
  ok: boolean;
  connected: boolean;
  provider: string;
}

export async function getOAuthStatus(
  provider: OAuthProvider,
  collection?: string
): Promise<OAuthStatusResponse> {
  const params = collection ? `?collection=${encodeURIComponent(collection)}` : "";
  return api.get(`/oauth/status/${provider}${params}`);
}

export function getOAuthStartUrl(
  provider: OAuthProvider,
  collection?: string
): string {
  const params = collection ? `?collection=${encodeURIComponent(collection)}` : "";
  return `/api/oauth/${provider}/start${params}`;
}

export async function disconnectOAuth(
  provider: OAuthProvider,
  collection?: string
): Promise<{ ok: boolean; disconnected: boolean }> {
  const params = collection ? `?collection=${encodeURIComponent(collection)}` : "";
  return api.post(`/oauth/${provider}/disconnect${params}`);
}
