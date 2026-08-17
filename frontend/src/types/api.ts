/** All response shapes mirror the Flask API in api/server.py. */

export type CortexRole = "admin" | "member" | "guest";

export interface BrainGrant {
  collection_name: string;
  role: CortexRole;
}

export interface MeResponse {
  ok: boolean;
  user: {
    id: string;
    email: string;
    name: string;
  };
  role: CortexRole;
  brains: BrainGrant[];
  app: { name: string };
}

export interface HomeCounts {
  entities: number;
  facts: number;
  relations: number;
  documents: number;
}

export interface Suggestion {
  id: string;
  prompt: string;
  source: string;
}

export interface RecentIntelligence {
  id: string;
  title: string;
  record_type: string;
  source_type: string;
  created_at: number | string;
}

export interface NeedsAttention {
  level: "warning" | "error" | "info";
  count: number;
  message: string;
}

export interface HomeResponse {
  ok: boolean;
  collection: string;
  available: boolean;
  reason?: string;
  counts: HomeCounts;
  suggestions: Suggestion[];
  recent: RecentIntelligence[];
  needs_attention: NeedsAttention[];
}

export interface OverviewStats {
  total_documents: number;
  total_entities: number;
  total_facts: number;
  total_relations: number;
  pending_merges: number;
  disputed_facts: number;
  last_ingestion_timestamp: number | string | null;
  source_type_breakdown: Record<string, number>;
}

export interface OverviewResponse {
  ok: boolean;
  collection: string;
  available: boolean;
  reason?: string;
  stats: OverviewStats;
  people_count: number;
  agents_count: number;
}

export interface KnowledgeItem {
  id: string;
  title: string;
  record_type: string;
  source_type: string;
  access_level: string;
  confidence?: number;
  created_at: number | string | null;
}

export interface KnowledgeResponse {
  ok: boolean;
  collection: string;
  total: number;
  items: KnowledgeItem[];
}

export interface SourcesResponse {
  ok: boolean;
  collection: string;
  total_documents: number;
  source_type_breakdown: Record<string, number>;
  last_ingestion_timestamp: number | string | null;
}

export interface AgentDeployment {
  platform: string;
  config: Record<string, unknown>;
  status: string;
  deployed_at: number;
}

export interface Agent {
  agent_id: string;
  agent_name: string;
  collection: string;
  role_default: string;
  created_at: number;
  deployments: AgentDeployment[];
}

export interface AgentsResponse {
  ok: boolean;
  items: Agent[];
}

export interface PersonAccessSummary {
  visible_documents: number;
  visible_facts: number;
  access_levels: string[];
}

export interface Person {
  employee_id: string;
  name: string;
  work_email: string;
  department?: string;
  role_title?: string;
  cortex_role: CortexRole;
  manager_employee_id?: string;
  linked_platforms: string[];
  access_summary: PersonAccessSummary;
}

export interface PeopleResponse {
  ok: boolean;
  collection: string;
  items: Person[];
}

export interface ActivityEvent {
  id: string;
  kind: "ingestion" | "deployment";
  title: string;
  created_at: number | string;
}

export interface ActivityResponse {
  ok: boolean;
  items: ActivityEvent[];
}

export interface AskResponse {
  ok: boolean;
  question: string;
  collection: string;
  answer: string;
  confidence: number;
  evidence: string[];
  abstained: boolean;
}

export interface HealthResponse {
  ok: boolean;
  service: string;
  hydradb: string;
  supabase: boolean;
  reasoning_provider: boolean;
}
