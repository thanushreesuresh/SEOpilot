import type { components } from "./api-types";
export type Audit = components["schemas"]["Audit"];
export type AuditSummary = components["schemas"]["AuditSummary"];
export type AuditRequest = components["schemas"]["AuditRequest"];
export type Issue = components["schemas"]["Issue"];
export type Recommendation = components["schemas"]["Recommendation"];
export type Page = components["schemas"]["Page"];
export type DecisionRequest = components["schemas"]["DecisionRequest"];
export type UsageStatus = components["schemas"]["UsageStatus"];
export const isActive = (audit: Audit) => ["queued", "crawling", "analyzing", "reviewing"].includes(audit.status);
async function request<T>(path: string, init?: RequestInit, onResponse?: (response: Response) => void): Promise<T> {
  let response: Response;
  try { response = await fetch(`/api${path}`, { cache: "no-store", ...init, headers: { "Content-Type": "application/json", ...init?.headers } }); }
  catch { throw new Error("Could not reach the audit service. Check that the backend is running on port 8000."); }
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    const detail = data?.detail;
    const message = typeof detail === "string" ? detail : Array.isArray(detail) ? detail.map((item: { msg: string }) => item.msg).join(". ") : "The audit service could not complete this request. Check that the backend is running and try again.";
    throw new Error(message);
  }
  onResponse?.(response);
  return response.json() as Promise<T>;
}
export const api = {
  usage: (signal?: AbortSignal) => request<UsageStatus>("/usage", { signal }),
  history: (signal?: AbortSignal) => request<AuditSummary[]>("/audits", { signal }),
  audit: (id: string, signal?: AbortSignal) => request<Audit>(`/audits/${encodeURIComponent(id)}`, { signal }),
  cancel: (id: string, signal?: AbortSignal) => request<Audit>(`/audits/${encodeURIComponent(id)}/cancel`, { method: "POST", body: "{}", signal }),
  create: async (data: AuditRequest) => {
    let reused = false;
    const audit = await request<Audit>("/audits", { method: "POST", body: JSON.stringify(data) }, (response) => { reused = response.headers.get("x-audit-reused") === "true"; });
    return { audit, reused };
  },
  demo: () => request<Audit>("/demo-audits", { method: "POST", body: "{}" }),
  decide: (id: string, data: DecisionRequest) => request<Recommendation>(`/recommendations/${encodeURIComponent(id)}/decision`, { method: "PATCH", body: JSON.stringify(data) }),
};
export function domain(url: string): string { try { return new URL(url).hostname; } catch { return url; } }
export function pagePath(url: string): string { try { const parsed = new URL(url); return parsed.pathname + parsed.search; } catch { return url; } }
export function dateTime(value: string): string { return new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value)); }
