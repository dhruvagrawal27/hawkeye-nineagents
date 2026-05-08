import axios from 'axios';

export const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || '/api';

export const api = axios.create({
  baseURL: apiBaseUrl,
  timeout: 30_000,
});

// Token interceptor — wired to the keycloak-js wrapper in lib/auth.ts.
let bearerProvider: () => string | null | undefined = () => null;
export function setBearerProvider(fn: () => string | null | undefined) {
  bearerProvider = fn;
}
api.interceptors.request.use((cfg) => {
  const token = bearerProvider();
  if (token) cfg.headers.Authorization = `Bearer ${token}`;
  return cfg;
});

export interface Alert {
  id: number;
  employee_id: string;
  account_id: string;
  score: number;
  display_score: number;
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  status: 'open' | 'investigating' | 'dismissed' | 'escalated';
  triggered_at: string;
  last_seen_at: string;
  assigned_to: string | null;
  top_signal: string | null;
  shap_factors: Array<{
    name: string;
    name_human: string;
    value: number;
    value_human: string;
    contribution: number;
    normal: string | null;
  }> | null;
  source: string;
}

export interface StatsOverview {
  total_alerts_24h: number;
  high_risk_employees: number;
  events_ingested: number;
  detection_latency_ms: number;
  alerts_open: number;
  alerts_dismissed: number;
  alerts_escalated: number;
  alerts_investigating: number;
  threshold: number;
  bands: Record<string, number>;
}

export const alertsApi = {
  list: (params: { limit?: number; status?: string; risk_level?: string; department?: string } = {}) =>
    api.get<Alert[]>('/alerts', { params }).then((r) => r.data),
  get: (id: number) => api.get<Alert>(`/alerts/${id}`).then((r) => r.data),
  triage: (id: number, action: 'dismiss' | 'investigate' | 'escalate' | 'reopen', note?: string) =>
    api.post<Alert>(`/alerts/${id}/triage`, { action, note }).then((r) => r.data),
  bulkTriage: (alert_ids: number[], action: 'dismiss' | 'investigate' | 'escalate' | 'reopen', note?: string) =>
    api.post<{ updated: number; action: string }>('/alerts/bulk-triage', { alert_ids, action, note }).then((r) => r.data),
  escalatedQueue: (limit = 50) =>
    api.get<Alert[]>('/alerts/queue/escalated', { params: { limit } }).then((r) => r.data),
  myQueue: (limit = 50) =>
    api.get<Alert[]>('/alerts/queue/mine', { params: { limit } }).then((r) => r.data),
};

export interface DeptRollup {
  department: string;
  total: number;
  open: number;
  investigating: number;
  escalated: number;
  dismissed: number;
  critical: number;
  high: number;
  max_score: number;
  mean_score: number;
  unique_employees: number;
}

export interface AuditEntry {
  id: number;
  alert_id: number | null;
  employee_id: string | null;
  actor: string;
  action: string;
  detail: string | null;
  occurred_at: string;
}

export const statsApi = {
  overview: () => api.get<StatsOverview>('/stats/overview').then((r) => r.data),
  riskDistribution: () =>
    api.get<Array<{ bin_low: number; bin_high: number; count: number }>>('/stats/risk-distribution').then((r) => r.data),
  ingestionRate: () => api.get('/stats/ingestion-rate').then((r) => r.data),
  byDepartment: () => api.get<DeptRollup[]>('/stats/by-department').then((r) => r.data),
  hourly: (hours = 168) =>
    api.get<Array<{ hour: string; LOW: number; MEDIUM: number; HIGH: number; CRITICAL: number; total: number }>>(
      '/stats/hourly',
      { params: { hours } },
    ).then((r) => r.data),
  auditLog: (limit = 50) => api.get<AuditEntry[]>('/stats/audit-log', { params: { limit } }).then((r) => r.data),
};

export interface Employee {
  id: string;
  account_id: string;
  display_name: string;
  department: string;
  is_mule_seed: number;
  risk_score: number | null;
  display_score: number | null;
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL' | null;
  open_alert_count: number;
}

export interface ScorePoint {
  recorded_at: string;
  score: number;
  display_score: number;
}

export interface GraphNode {
  id: string;
  label: 'Employee' | 'System';
  risk_score: number;
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  department: string | null;
  kind: string | null;
  access_count: number | null;
}

export interface GraphEdge {
  source: string;
  target: string;
  count: number;
  last_at: string | null;
}

export interface GraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export const employeesApi = {
  list: (params: { limit?: number; department?: string; risk_min?: number } = {}) =>
    api.get<Employee[]>('/employees', { params }).then((r) => r.data),
  top: (limit = 10) =>
    api.get<Employee[]>('/employees/top', { params: { limit } }).then((r) => r.data),
  get: (id: string) => api.get<Employee>(`/employees/${id}`).then((r) => r.data),
  scoreHistory: (id: string, days = 30) =>
    api.get<ScorePoint[]>(`/employees/${id}/score-history`, { params: { days } }).then((r) => r.data),
  alerts: (id: string, limit = 50) =>
    api.get<Alert[]>(`/employees/${id}/alerts`, { params: { limit } }).then((r) => r.data),
};

export const graphApi = {
  neighbourhood: (id: string, depth = 2) =>
    api.get<GraphResponse>(`/graph/${id}`, { params: { depth } }).then((r) => r.data),
  overview: (minScore = 0.16, limit = 200) =>
    api.get<GraphResponse>('/graph', { params: { min_score: minScore, limit } }).then((r) => r.data),
  hubs: (topN = 10) =>
    api.get<Array<{ system_id: string; flagged_users: number; sample_users: string[] }>>('/graph/hubs', {
      params: { top_n: topN },
    }).then((r) => r.data),
};

export const narrativeApi = {
  get: (alertId: number) =>
    api.get<{
      alert_id: number;
      body: string;
      model_version: string;
      is_fallback: boolean;
      latency_ms: number | null;
      generated_at: string;
    }>(`/narrative/${alertId}`).then((r) => r.data),
  regenerate: (alertId: number) =>
    api.post<{
      alert_id: number;
      body: string;
      model_version: string;
      is_fallback: boolean;
      latency_ms: number | null;
      generated_at: string;
    }>(`/narrative/${alertId}/regenerate`).then((r) => r.data),
};

export const settingsApi = {
  modelCard: () => api.get('/stats/model-card').then((r) => r.data),
  ready: () => api.get('/readyz').then((r) => r.data),
};

export const replayApi = {
  start: (mode: 'mule_burst' | 'sequential' = 'mule_burst', rate = 500) =>
    api.post('/replay/start', { mode, rate }).then((r) => r.data),
  stop: () => api.post('/replay/stop').then((r) => r.data),
  injectBurst: () => api.post('/replay/inject-burst').then((r) => r.data),
  status: () => api.get('/replay/status').then((r) => r.data),
};
