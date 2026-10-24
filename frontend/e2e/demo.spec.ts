import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import type { Audit, AuditSummary } from "../src/lib/api";
import { sampleAudit } from "./fixtures";

const OLD_ID = "99999999-9999-4999-8999-999999999999";
const CURRENT_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const OLD_DATE = "2026-10-20T12:00:00Z";

async function upgradeFixture(page: Page, request: APIRequestContext, failFirst = false) {
  const source = await sampleAudit(request);
  const current: Audit = { ...source, id: CURRENT_ID, created_at: "2026-10-25T12:00:00Z" };
  const legacy: Audit = { ...source, id: OLD_ID, demo_revision: null, created_at: OLD_DATE,
    discovery: null, score: { ...source.score, breakdown: null },
    recommendations: source.recommendations.map((item, index) => ({ ...item, status: index ? "pending" : "approved",
      decided_at: index ? null : OLD_DATE })),
  };
  const state = { openedCurrent: false, attempts: 0, unexpected: [] as string[] };
  await page.route("**/api/**", (route) => {
    const method = route.request().method(), path = new URL(route.request().url()).pathname;
    if (path === "/api/usage" && method === "GET") return route.fulfill({ json: { limit: 3, used: 3, remaining: 0,
      reset_at: "2026-10-26T00:00:00Z", retry_after: 600, window_hours: 24, ai_enabled: false, ai_calls_remaining: 14 } });
    if (path === "/api/audits" && method === "GET") {
      const audits = state.openedCurrent ? [current, legacy] : [legacy];
      const history: AuditSummary[] = audits.map((audit) => ({ id: audit.id, url: audit.url, mode: audit.mode,
        status: audit.status, created_at: audit.created_at, score: audit.score.value, pages: audit.pages.length, issues: audit.issues.length }));
      return route.fulfill({ json: history });
    }
    if (path === "/api/demo-audits" && method === "POST") {
      expect(route.request().postDataJSON()).toEqual({});
      state.attempts += 1;
      if (failFirst && state.attempts === 1) return route.fulfill({ status: 503, json: { detail: "Current sample could not be opened. Try again." } });
      state.openedCurrent = true;
      return route.fulfill({ status: 201, json: current });
    }
    if (path === `/api/audits/${OLD_ID}` && method === "GET") return route.fulfill({ json: legacy });
    if (path === `/api/audits/${CURRENT_ID}` && method === "GET") return route.fulfill({ json: current });
    if (/^\/api\/audits\/[^/]+\/dispositions$/.test(path) && method === "GET") return route.fulfill({ json: [] });
    state.unexpected.push(`${method} ${path}`);
    return route.fulfill({ status: 500, json: { detail: "Unexpected sample upgrade fixture request" } });
  });
  return { state, current };
}

test("current offline sample exposes its revision and report provenance", async ({ page, request }) => {
  const audit = await sampleAudit(request);
  expect(audit.demo_revision).toBeTruthy();
  expect(audit.allow_ai).toBe(false);
  await page.goto(`/?audit=${audit.id}`);
  await expect(page.locator(".sample-revision")).toHaveText(`Fixture revision ${audit.demo_revision}. Saved decisions belong to this sample.`);
  const response = await request.get(`/api/audits/${audit.id}/report/json`);
  expect(response.ok()).toBe(true);
  const report = await response.json();
  expect(JSON.parse(report.content).demo_revision).toBe(audit.demo_revision);
});

test("opening current fixtures preserves the historical sample and exhausted allowance", async ({ page, request }) => {
  const { state, current } = await upgradeFixture(page, request);
  await page.goto(`/?audit=${OLD_ID}`);
  await expect(page.locator(".sample-revision")).toContainText("Historical sample: fixture revision not recorded.");
  await expect(page.getByRole("button", { name: "Run audit", exact: true })).toBeDisabled();
  await page.getByRole("button", { name: "Explore sample audit", exact: true }).click();
  await expect(page).toHaveURL(new RegExp(CURRENT_ID));
  await expect(page.locator(".sample-revision")).toContainText(`Fixture revision ${current.demo_revision}.`);
  await expect(page.getByText("0 of 3 live audits left", { exact: true })).toBeVisible();
  await page.getByText("How is the score calculated?", { exact: true }).click();
  await expect(page.getByRole("heading", { name: "Sample score calculation", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Audit history", exact: true }).click();
  await expect(page.getByRole("button", { name: "Open audit", exact: true })).toHaveCount(2);
  await page.getByRole("button", { name: "Open audit", exact: true }).nth(1).click();
  await expect(page).toHaveURL(new RegExp(OLD_ID));
  await expect(page.locator(".sample-revision")).toContainText("Historical sample: fixture revision not recorded.");
  await expect(page.getByText("Approved", { exact: true }).first()).toBeVisible();
  expect(state.attempts).toBe(1);
  expect(state.unexpected).toEqual([]);
});

test("mobile sample upgrade failure can retry through the keyboard without losing history", async ({ page, request }, testInfo) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const { state } = await upgradeFixture(page, request, true);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`/?audit=${OLD_ID}`);
  const open = page.getByRole("button", { name: "Explore sample audit", exact: true });
  await expect(open).toBeEnabled();
  await open.focus();
  await expect(open).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("alert").filter({ hasText: "Current sample could not be opened" })).toBeVisible();
  await expect(page).toHaveURL(new RegExp(OLD_ID));
  await expect(page.locator(".sample-revision")).toContainText("Historical sample:");
  await expect(open).toBeEnabled();
  await open.focus();
  await expect(open).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(new RegExp(CURRENT_ID));
  await expect(page.locator(".sample-revision")).toContainText("Fixture revision");
  await expect(page.getByRole("alert").filter({ hasText: "Current sample could not be opened" })).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("sample-upgrade-mobile.png"), fullPage: true });
  expect(state.attempts).toBe(2);
  expect(state.unexpected).toEqual([]);
  expect(errors).toEqual([]);
});
