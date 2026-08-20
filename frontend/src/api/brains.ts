import { api } from "@/lib/api";

export interface CreateBrainResponse {
  ok: boolean;
  collection_name: string;
  status: string;
  employees_added: number;
  employees_updated: number;
}

export interface AcceptInvitationResponse {
  ok: boolean;
  status: string;
  collection: string;
  employee_id?: string;
  role?: string;
}

export async function createBrain(orgName: string): Promise<CreateBrainResponse> {
  return api.post<CreateBrainResponse>("/brains", { org_name: orgName });
}

export async function acceptInvitation(token: string): Promise<AcceptInvitationResponse> {
  return api.post<AcceptInvitationResponse>(`/invitations/${token}/accept`);
}

export async function deleteBrain(collectionName: string): Promise<{ ok: boolean; removed: string }> {
  return api.delete<{ ok: boolean; removed: string }>(`/brains/${encodeURIComponent(collectionName)}`);
}
