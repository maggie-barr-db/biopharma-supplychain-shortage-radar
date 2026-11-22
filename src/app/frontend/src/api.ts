export type Row = Record<string, string | number | boolean | null>;

// Databricks Apps answers an expired session (or newly requested permissions) with a redirect to sign-in,
// which fetch cannot follow. Detect it and reload once so the browser signs in again.
function reauth(): never {
  if (!sessionStorage.getItem("radar-reauth")) {
    sessionStorage.setItem("radar-reauth", "1");
    window.location.reload();
  }
  throw new Error("Your sign-in needs refreshing. Reload the page to continue.");
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let r: Response;
  try {
    r = await fetch(path, { headers: { "Content-Type": "application/json" }, redirect: "manual", ...init });
  } catch {
    return reauth();
  }
  if (r.type === "opaqueredirect" || r.status === 0 || r.status === 401) return reauth();
  sessionStorage.removeItem("radar-reauth");
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
  return r.json();
}

export type AskResult = { route: string; answer: string; rows: Row[] | null; session_id?: string; fallback_reason?: string; seconds: number };
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
  ask: (question: string, session_id?: string, context?: string) =>
    call<AskResult>("/api/ask", { method: "POST", body: JSON.stringify({ question, session_id, context }) }),
};
