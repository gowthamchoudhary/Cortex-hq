import { api } from "@/lib/api";

export interface OAuthStatusResponse {
  ok: boolean;
  connected: boolean;
  provider: string;
}

export async function getOAuthStatus(
  provider: "gmail" | "slack",
  collection?: string
): Promise<OAuthStatusResponse> {
  const params = collection ? `?collection=${encodeURIComponent(collection)}` : "";
  return api.get(`/oauth/status/${provider}${params}`);
}

export function getOAuthStartUrl(
  provider: "gmail" | "slack",
  collection?: string
): string {
  const params = collection ? `?collection=${encodeURIComponent(collection)}` : "";
  return `/api/oauth/${provider}/start${params}`;
}

export async function disconnectOAuth(
  provider: "gmail" | "slack",
  collection?: string
): Promise<{ ok: boolean; disconnected: boolean }> {
  const params = collection ? `?collection=${encodeURIComponent(collection)}` : "";
  return api.post(`/oauth/${provider}/disconnect${params}`);
}
