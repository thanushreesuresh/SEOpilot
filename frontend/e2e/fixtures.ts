import { expect, type APIRequestContext } from "@playwright/test";
import type { Audit, AuditSummary } from "../src/lib/api";

export async function sampleAudit(request: APIRequestContext): Promise<Audit> {
  // Read saved fixtures first: redundant creation requests still count against
  // the production burst guard. Keep this helper usable when a spec runs alone.
  const historyResponse = await request.get("/api/audits");
  expect(historyResponse.ok(), `Fixture history returned HTTP ${historyResponse.status()}`).toBe(true);
  const history: AuditSummary[] = await historyResponse.json();
  const saved = history.find((audit) => audit.mode === "demo");
  const response = saved ? await request.get(`/api/audits/${saved.id}`) : await request.post("/api/demo-audits", { data: {} });
  expect(response.ok(), `Sample fixture returned HTTP ${response.status()}`).toBe(true);
  return response.json();
}
