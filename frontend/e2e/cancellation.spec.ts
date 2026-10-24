import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import type { Audit, AuditSummary } from "../src/lib/api";
import { sampleAudit } from "./fixtures";

const ID = "77777777-7777-4777-8777-777777777777";

async function cancellationFixture(page: Page, request: APIRequestContext, status: "queued" | "crawling" | "reviewing") {
  const sample = await sampleAudit(request);
  let current: Audit = { ...sample, id: ID, mode: "live", url: "https://cancel.example.com/", origin: "https://cancel.example.com",
    status, ai_status: status === "reviewing" ? "pending" : "unavailable", allow_ai: true, completed_at: null,
    progress: { stage: status, visited: status === "queued" ? 0 : 1, discovered: 1, limit: 15, message: "Audit fixture in progress" },
    pages: status === "queued" ? [] : [{ ...sample.pages[0], url: "https://cancel.example.com/", title: "Collected page evidence" }],
    issues: [], recommendations: [], warnings: [], summary: "Saved cancellation fixture.",
    coverage: { attempted: status === "reviewing" ? 1 : 0, assessed: status === "reviewing" ? 1 : 0, failed: 0, blocked: 0, unchecked: 0, truncated: false },
    score: { ...sample.score, value: null, assessed_pages: 0, breakdown: null },
  };
  const state = { cancelRequests: 0, failNext: false, unexpected: [] as string[] };
  await page.route("**/api/**", async (route) => {
    const method = route.request().method();
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/usage") return route.fulfill({ json: { limit: 3, used: 1, remaining: 2, reset_at: null,
      retry_after: 0, window_hours: 24, ai_enabled: true, ai_calls_remaining: 19 } });
    if (path === "/api/audits" && method === "GET") {
      const summary: AuditSummary = { id: ID, url: current.url, mode: "live", status: current.status,
        created_at: current.created_at, score: null, pages: current.pages.length, issues: 0 };
      return route.fulfill({ json: [summary] });
    }
    if (path === `/api/audits/${ID}` && method === "GET") return route.fulfill({ json: current });
    if (path === `/api/audits/${ID}/cancel` && method === "POST") {
      state.cancelRequests += 1;
      expect(route.request().postDataJSON()).toEqual({});
      if (state.failNext) {
        state.failNext = false;
        return route.fulfill({ status: 503, json: { detail: "Cancellation could not be confirmed. Try again." } });
      }
      current = { ...current, status: "cancelled", completed_at: "2026-10-25T04:00:00Z",
        ai_status: current.status === "reviewing" ? "cancelled" : current.ai_status,
        progress: { ...current.progress, stage: "cancelled", message: "Cancelled by you" },
        warnings: ["The accepted admission and AI reservations remain charged."] };
      return route.fulfill({ json: current });
    }
    state.unexpected.push(`${method} ${path}`);
    return route.fulfill({ status: 500, json: { detail: "Unexpected cancellation fixture request" } });
  });
  return state;
}

test("queued audit can be cancelled without refunding allowance and remains in history", async ({ page, request }) => {
  const state = await cancellationFixture(page, request, "queued");
  await page.goto(`/?audit=${ID}`);
  await expect(page.getByRole("status", { name: "Audit progress", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Cancel audit", exact: true }).click();
  await expect(page.getByText(/Audit cancelled\. These are retained, incomplete results/)).toBeVisible();
  await expect(page.getByRole("status", { name: "Audit progress", exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Cancel audit", exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Download report", exact: true })).toBeEnabled();
  await expect(page.getByText("2 of 3 live audits left", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Audit history", exact: true }).click();
  await expect(page.getByRole("row").filter({ hasText: "cancel.example.com" }).getByText("cancelled", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Open audit", exact: true }).click();
  await expect(page.getByText(/Audit cancelled\. These are retained, incomplete results/)).toBeVisible();
  expect(state.cancelRequests).toBe(1);
  expect(state.unexpected).toEqual([]);
});

test("failed cancellation remains active and a retry confirms the stop", async ({ page, request }) => {
  const state = await cancellationFixture(page, request, "crawling");
  state.failNext = true;
  await page.goto(`/?audit=${ID}`);
  await page.getByRole("button", { name: "Cancel audit", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Cancellation could not be confirmed" })).toBeVisible();
  await expect(page.getByRole("status", { name: "Audit progress", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Cancel audit", exact: true }).click();
  await expect(page.getByText(/Audit cancelled\. These are retained, incomplete results/)).toBeVisible();
  await expect(page.getByRole("alert").filter({ hasText: "Cancellation could not be confirmed" })).toHaveCount(0);
  expect(state.cancelRequests).toBe(2);
  expect(state.unexpected).toEqual([]);
});

test("mobile keyboard cancellation during AI review preserves collected pages", async ({ page, request }, testInfo) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const state = await cancellationFixture(page, request, "reviewing");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`/?audit=${ID}`);
  await expect(page.getByText(/An AI request already in progress may still be billed/)).toBeVisible();
  await page.getByRole("button", { name: "Cancel audit", exact: true }).focus();
  await page.keyboard.press("Enter");
  await expect(page.getByText(/Audit cancelled\. These are retained, incomplete results/)).toBeVisible();
  await page.getByRole("tab", { name: "Recommendations", exact: true }).click();
  await expect(page.getByText(/AI processing was cancelled/)).toBeVisible();
  await page.getByRole("tab", { name: "Pages", exact: true }).click();
  await expect(page.getByRole("cell").filter({ hasText: "Collected page evidence" })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("audit-cancel-mobile.png"), fullPage: true });
  expect(state.cancelRequests).toBe(1);
  expect(state.unexpected).toEqual([]);
  expect(errors).toEqual([]);
});
