import type { components } from "./api-types";

export type AuditReport = components["schemas"]["AuditReport"];
export type AuditComparison = components["schemas"]["AuditComparison"];
export type FindingChange = components["schemas"]["FindingChange"];
export type ComparisonRequest = components["schemas"]["ComparisonRequest"];
export type ReportFormat = "markdown" | "csv" | "json";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, { cache: "no-store", ...init, headers: { "Content-Type": "application/json", ...init?.headers } });
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === "AbortError") throw cause;
    throw new Error("Could not reach the reporting service. Check that the backend is running and try again.");
  }
  const data: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = data && typeof data === "object" && "detail" in data ? data.detail : null;
    throw new Error(typeof detail === "string" ? detail : "Could not prepare this report or comparison. Refresh and try again.");
  }
  if (!data) throw new Error("The reporting service returned an empty response. Try again.");
  return data as T;
}

export const reportingApi = {
  report: (auditId: string, format: ReportFormat, signal?: AbortSignal) => request<AuditReport>(`/audits/${encodeURIComponent(auditId)}/report/${format}`, { signal }),
  compare: (data: ComparisonRequest, signal?: AbortSignal) => request<AuditComparison>("/audit-comparisons", { method: "POST", body: JSON.stringify(data), signal }),
};
