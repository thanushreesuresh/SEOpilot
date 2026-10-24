import type { components } from "./api-types";

export type ConnectionStatus = components["schemas"]["ConnectionStatus"];
export type Project = components["schemas"]["Project"];
export type ProjectRequest = components["schemas"]["ProjectRequest"];
export type FixRun = components["schemas"]["FixRun"];
export type FixRequest = components["schemas"]["FixRequest"];
export type PatchExport = components["schemas"]["PatchExport"];
export type FindingDisposition = components["schemas"]["FindingDisposition"];
export type DispositionRequest = components["schemas"]["DispositionRequest"];

function errorMessage(data: unknown): string {
  if (data && typeof data === "object" && "detail" in data) {
    const detail = data.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) return detail.map((item: unknown) => item && typeof item === "object" && "msg" in item && typeof item.msg === "string" ? item.msg : "Invalid request").join(". ");
  }
  return "The workspace could not complete this request. Refresh and try again.";
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try { response = await fetch(`/api${path}`, { cache: "no-store", ...init, headers: {"Content-Type": "application/json", ...init?.headers} }); }
  catch (cause) {
    if (cause instanceof DOMException && cause.name === "AbortError") throw cause;
    throw new Error("Could not reach the workspace service. Check that the backend is running.");
  }
  const data: unknown = await response.json().catch(() => null);
  if (!response.ok) throw new Error(errorMessage(data));
  return data as T;
}

const idPath = (id: string) => encodeURIComponent(id);
const post = (data: unknown = {}) => ({method: "POST", body: JSON.stringify(data)});
export const fixApi = {
  connection: (signal?: AbortSignal) => request<ConnectionStatus>("/github/connection", {signal}),
  projects: (signal?: AbortSignal) => request<Project[]>("/projects", {signal}),
  createProject: (data: ProjectRequest) => request<Project>("/projects", post(data)),
  disconnect: (id: string) => request<Project>(`/projects/${idPath(id)}/disconnect`, post()),
  runs: async (projectId: string, signal?: AbortSignal) => (await request<FixRun[]>("/fix-runs", {signal})).filter((run) => run.project_id === projectId),
  run: (id: string, signal?: AbortSignal) => request<FixRun>(`/fix-runs/${idPath(id)}`, {signal}),
  refresh: (id: string) => request<FixRun>(`/fix-runs/${idPath(id)}/refresh`, post()),
  create: (data: FixRequest) => request<FixRun>("/fix-runs", post(data)),
  patch: (id: string) => request<PatchExport>(`/fix-runs/${idPath(id)}/patch`),
  publish: (id: string, patch_hash: string) => request<FixRun>(`/fix-runs/${idPath(id)}/publish`, post({patch_hash, confirms_publication: true})),
  cancel: (id: string) => request<FixRun>(`/fix-runs/${idPath(id)}/cancel`, post()),
  deleteSource: (id: string) => request<FixRun>(`/fix-runs/${idPath(id)}/delete-source`, post()),
  verify: (id: string) => request<FixRun>(`/fix-runs/${idPath(id)}/verify`, post()),
  dispositions: (auditId: string, signal?: AbortSignal) => request<FindingDisposition[]>(`/audits/${idPath(auditId)}/dispositions`, {signal}),
  disposition: (auditId: string, issueId: string, data: DispositionRequest) => request<FindingDisposition>(`/audits/${idPath(auditId)}/issues/${idPath(issueId)}/disposition`, {method: "PATCH", body: JSON.stringify(data)}),
};
