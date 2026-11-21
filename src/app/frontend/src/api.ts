export type Row = Record<string, string | number | boolean | null>;
async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, { headers: { "Content-Type": "application/json" }, ...init });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
  return r.json();
}
export const api = {
  me: () => call<Row>("/api/me"),
  kpis: () => call<Row[]>("/api/kpis"),
  disruptions: () => call<Row[]>("/api/disruptions"),
  disruption: (id: string) => call<Row[]>(`/api/disruptions/${encodeURIComponent(id)}`),
  actions: () => call<Row[]>("/api/actions"),
  audit: (id: number) => call<Row[]>(`/api/actions/${id}/audit`),
  propose: (body: object) => call<Row>("/api/actions", { method: "POST", body: JSON.stringify(body) }),
  decide: (id: number, status: string, rationale: string) =>
    call<Row>(`/api/actions/${id}/decision`, { method: "POST", body: JSON.stringify({ status, rationale }) }),
  ask: (question: string, session_id?: string) =>
    call<{ route: string; answer: string; rows: Row[] | null; session_id?: string; fallback_reason?: string; seconds: number }>(
      "/api/ask", { method: "POST", body: JSON.stringify({ question, session_id }) }),
};
