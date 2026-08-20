import { api } from "@/lib/api";
import type { Person } from "@/types/api";

export async function fetchPeople(
  collection?: string
): Promise<{ items: Person[] }> {
  const params = collection ? `?collection=${encodeURIComponent(collection)}` : "";
  return api.get(`/people${params}`);
}

export interface EmployeeRegistration {
  name: string;
  work_email: string;
  employee_id?: string;
  cortex_role?: string;
  department?: string;
  role_title?: string;
}

export interface InvitationResult {
  ok: boolean;
  token?: string;
  invite_url?: string;
  employee_id?: string;
  collection?: string;
  status?: string;
  created_at?: string;
  expires_at?: string;
}

export async function registerEmployee(
  collection: string | undefined,
  employee: EmployeeRegistration
): Promise<{ ok: boolean; employee?: Record<string, unknown> }> {
  const params = collection ? `?collection=${encodeURIComponent(collection)}` : "";
  return api.post(`/employees${params}`, employee);
}

export async function createInvitation(
  collection: string | undefined,
  employeeId: string
): Promise<InvitationResult> {
  const params = collection ? `?collection=${encodeURIComponent(collection)}` : "";
  return api.post(`/invitations${params}`, { employee_id: employeeId });
}
