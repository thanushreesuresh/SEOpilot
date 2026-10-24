import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import type { Audit, AuditSummary } from "../src/lib/api";
import { sampleAudit } from "./fixtures";

const ID = "88888888-8888-4888-8888-888888888888";
const ORIGIN = "https://discovery.example.com";
const CANARY = '<img src=x onerror="window.discoveryCanary=true">';

async function discoveryFixture(page: Page, request: APIRequestContext, legacy = false) {
  const sample = await sampleAudit(request);
  const audit: Audit = { ...sample, id: ID, mode: "live", status: "partial", url: ORIGIN + "/", origin: ORIGIN,
    discovery: legacy ? null : { robots_state: "present", sitemap_state: "unknown", request_attempts: 5,
      effective_delay_seconds: 2, notes: ["An external-origin sitemap declaration was skipped."], probes: [
        { kind: "robots", url: ORIGIN + "/robots.txt", outcome: "present", status_code: 200, explanation: "A usable robots policy was parsed." },
        { kind: "sitemap", url: ORIGIN + "/sitemap.xml", outcome: "blocked", status_code: null, explanation: "robots.txt disallows this location; no request was made." },
        { kind: "sitemap", url: ORIGIN + "/map.xml", outcome: "unknown", status_code: 200, explanation: CANARY },
      ] },
  };
  const unexpected: string[] = [];
  await page.route("**/api/**", (route) => {
    const method = route.request().method();
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/usage" && method === "GET") return route.fulfill({ json: { limit: 3, used: 1, remaining: 2,
      reset_at: null, retry_after: 0, window_hours: 24, ai_enabled: false, ai_calls_remaining: 20 } });
    if (path === "/api/audits" && method === "GET") {
      const summary: AuditSummary = { id: ID, url: audit.url, mode: audit.mode, status: audit.status,
        created_at: audit.created_at, score: audit.score.value, pages: audit.pages.length, issues: audit.issues.length };
      return route.fulfill({ json: [summary] });
    }
    if (path === `/api/audits/${ID}` && method === "GET") return route.fulfill({ json: audit });
    if (path === `/api/audits/${ID}/dispositions` && method === "GET") return route.fulfill({ json: [] });
    unexpected.push(`${method} ${path}`);
    return route.fulfill({ status: 500, json: { detail: "Unexpected discovery fixture request" } });
  });
  return unexpected;
}

test("saved discovery checks distinguish blocked and invalid responses and escape evidence", async ({ page, request }, testInfo) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const unexpected = await discoveryFixture(page, request);
  await page.goto(`/?audit=${ID}`);
  await expect(page).toHaveTitle(/SEOPilot/);
  const panel = page.getByRole("region", { name: "Crawl discovery", exact: true });
  await expect(panel.getByText(/Robots policy: present · Sitemap: unknown/)).toBeVisible();
  await panel.getByText("Inspect crawl discovery evidence", { exact: true }).click();
  await expect(panel.getByText(/5 budgeted request attempts/)).toBeVisible();
  await expect(panel.getByText(/Effective minimum delay: 2 seconds/)).toBeVisible();
  await expect(panel.getByText("Sitemap: blocked", { exact: true })).toBeVisible();
  await expect(panel.getByText(CANARY, { exact: true })).toBeVisible();
  await expect(panel.locator("img")).toHaveCount(0);
  expect(await page.evaluate(() => "discoveryCanary" in window)).toBe(false);
  await expect(panel.getByText(/Listed sitemap URLs and search-engine indexing were not verified/)).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("crawl-discovery-desktop.png"), fullPage: true });
  expect(unexpected).toEqual([]);
  expect(errors).toEqual([]);
});

test("mobile keyboard can expand saved discovery evidence without horizontal overflow", async ({ page, request }, testInfo) => {
  const unexpected = await discoveryFixture(page, request);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`/?audit=${ID}`);
  const panel = page.getByRole("region", { name: "Crawl discovery", exact: true });
  await panel.getByText("Inspect crawl discovery evidence", { exact: true }).focus();
  await page.keyboard.press("Enter");
  await expect(panel.getByText("An external-origin sitemap declaration was skipped.", { exact: true })).toBeVisible();
  await expect(panel.getByRole("link", { name: ORIGIN + "/robots.txt", exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("crawl-discovery-mobile.png"), fullPage: true });
  await page.keyboard.press("Enter");
  await expect(panel.getByText(/5 budgeted request attempts/)).toBeHidden();
  expect(unexpected).toEqual([]);
});

test("legacy audit explicitly reports unrecorded discovery checks", async ({ page, request }) => {
  const unexpected = await discoveryFixture(page, request, true);
  await page.goto(`/?audit=${ID}`);
  const panel = page.getByRole("region", { name: "Crawl discovery", exact: true });
  await expect(panel.getByText("Discovery checks were not recorded for this audit; their outcomes remain unknown.", { exact: true })).toBeVisible();
  await expect(panel.getByText("Inspect crawl discovery evidence", { exact: true })).toHaveCount(0);
  expect(unexpected).toEqual([]);
});
