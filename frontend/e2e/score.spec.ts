import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import type { Audit } from "../src/lib/api";

const CANARY = '<img src=x onerror="window.scoreCanary=true">';

async function sampleAudit(request: APIRequestContext): Promise<Audit> {
  const response = await request.post("/api/demo-audits", { data: {} });
  expect(response.ok()).toBe(true);
  return response.json();
}

async function openScore(page: Page, audit: Audit) {
  await page.goto(`/?audit=${audit.id}`);
  await expect(page).toHaveTitle(/SEOPilot/);
  await page.getByText("How is the score calculated?", { exact: true }).click();
  return page.getByRole("region", { name: "Score deductions", exact: true });
}

test("sample score explains averaging and HTTP overrides then links back to evidence", async ({ page, request }, testInfo) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const audit = await sampleAudit(request);
  const panel = await openScore(page, audit);
  await expect(panel.getByRole("heading", { name: "Sample score calculation", exact: true })).toBeVisible();
  await expect(panel.getByText(/Page penalties are averaged across 4 assessed pages/)).toBeVisible();
  await expect(panel.getByText(/with ties to even/)).toBeVisible();
  const broken = panel.locator("details").filter({ hasText: "/old-collection" });
  await broken.locator("summary").click();
  await expect(broken.getByText(/HTTP-error override: the page penalty is 100/)).toBeVisible();
  await expect(broken.getByText("100 / 100 page penalty", { exact: true })).toBeVisible();
  await expect(panel.getByRole("heading", { name: "Site deductions", exact: true })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("score-breakdown-desktop.png"), fullPage: true });
  await broken.getByRole("button", { name: "Search this URL in findings", exact: true }).click();
  await expect(page.getByRole("searchbox", { name: "Search URLs", exact: true })).toHaveValue("https://northstar-pottery.example/old-collection");
  await expect(page.getByRole("tab", { name: "Issues", exact: true })).toBeFocused();
  await expect(page.getByRole("button", { name: "Page returned an HTTP error", exact: true })).toBeVisible();
  expect(errors).toEqual([]);
});

test("mobile score details support keyboard and escape rule text", async ({ page, request }, testInfo) => {
  const audit = await sampleAudit(request);
  expect(audit.score.breakdown).not.toBeNull();
  audit.score.breakdown!.pages[0].rules[0].title = CANARY;
  await page.route(`**/api/audits/${audit.id}`, (route) => route.fulfill({ json: audit }));
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`/?audit=${audit.id}`);
  await page.getByText("How is the score calculated?", { exact: true }).focus();
  await page.keyboard.press("Enter");
  const panel = page.getByRole("region", { name: "Score deductions", exact: true });
  const first = panel.locator("details").first();
  await first.locator("summary").focus();
  await page.keyboard.press("Enter");
  await expect(first.getByText(CANARY, { exact: true })).toBeVisible();
  await expect(first.locator("img")).toHaveCount(0);
  expect(await page.evaluate(() => "scoreCanary" in window)).toBe(false);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("score-breakdown-mobile.png"), fullPage: true });
  await page.keyboard.press("Enter");
  await expect(first.getByText(CANARY, { exact: true })).toBeHidden();
});

test("historical score without a breakdown stays unchanged and explicitly unrecorded", async ({ page, request }) => {
  const audit = await sampleAudit(request);
  audit.score.breakdown = null;
  await page.route(`**/api/audits/${audit.id}`, (route) => route.fulfill({ json: audit }));
  await page.goto(`/?audit=${audit.id}`);
  await page.getByText("How is the score calculated?", { exact: true }).click();
  await expect(page.getByText("A score breakdown was not recorded; the historical score has not been recalculated.", { exact: true })).toBeVisible();
  await expect(page.getByRole("region", { name: "Score deductions", exact: true })).toHaveCount(0);
  await expect(page.locator(".health-metric .metric-value")).toContainText(String(audit.score.value));
});

test("unassessed score explains excluded pages without rendering zero as success", async ({ page, request }) => {
  const audit = await sampleAudit(request);
  const blocked = { ...audit.pages[0], outcome: "blocked" as const, status_code: null, error: "robots.txt disallows this URL." };
  const unassessed: Audit = { ...audit, status: "failed", pages: [blocked], issues: [], recommendations: [],
    score: { ...audit.score, value: null, assessed_pages: 0, breakdown: { pages: [], site_rules: [],
      excluded_pages: [{ page_id: blocked.id, url: blocked.url, outcome: "blocked", status_code: null }],
      mean_page_penalty: null, site_rule_points: 0, site_penalty: 0, unrounded_value: null } },
    coverage: { attempted: 1, assessed: 0, blocked: 1, failed: 0, unchecked: 0, truncated: false },
  };
  await page.route(`**/api/audits/${audit.id}`, (route) => route.fulfill({ json: unassessed }));
  const panel = await openScore(page, unassessed);
  await expect(panel.getByText("No assessed pages means no score. Excluded pages do not improve the denominator.", { exact: true })).toBeVisible();
  await expect(panel.getByText("blocked · HTTP not recorded", { exact: true })).toBeVisible();
  await expect(panel.getByText("Mean page penalty", { exact: true })).toHaveCount(0);
  await expect(page.locator(".health-metric .metric-value")).toContainText("—");
});
