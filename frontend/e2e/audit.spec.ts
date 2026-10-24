import { expect, test } from "@playwright/test";

test("sample audit, filters, evidence, decisions and history persist", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await expect(page).toHaveTitle(/SEOPilot/i);
  await expect(page.getByRole("heading", { name: "Your next move in search." })).toBeVisible();
  await page.getByRole("button", { name: "Explore sample audit" }).click();
  await expect(page.getByText("Sample audit", { exact: true }).first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Approve", exact: true }).first()).toBeVisible();
  await page.getByRole("button", { name: "Approve", exact: true }).first().click();
  await expect(page.getByText(/Approved/).first()).toBeVisible();
  const resultUrl = page.url();
  await page.reload();
  await expect(page.getByText(/Approved/).first()).toBeVisible();
  await page.getByRole("button", { name: "Reject", exact: true }).first().click();
  await expect(page.getByText(/Rejected/).first()).toBeVisible();
  await page.getByRole("combobox", { name: "Severity", exact: true }).selectOption("High");
  await expect(page.getByText("Page returned an HTTP error").first()).toBeVisible();
  await page.getByRole("textbox", { name: "Search URLs", exact: true }).fill("no-such-fixture-page");
  await expect(page.getByText(/No .*match|No findings|No issues/i).first()).toBeVisible();
  await page.getByRole("textbox", { name: "Search URLs", exact: true }).fill("");
  await page.getByRole("button", { name: "Audit history", exact: true }).click();
  await expect(page.getByRole("heading", { name: /Audit history/i })).toBeVisible();
  await page.goto(resultUrl);
  await expect(page.getByText(/Rejected/).first()).toBeVisible();
  expect(errors).toEqual([]);
});

test("restricted URL is rejected without a crawl", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("textbox", { name: "Website URL", exact: true }).fill("http://127.0.0.1/");
  await page.getByRole("button", { name: "Run audit", exact: true }).click();
  await expect(page.getByRole("alert")).toBeVisible();
  await expect(page.getByRole("alert")).toContainText(/public|restricted|private|local|not allowed|not permitted/i);
});

test("mobile dashboard remains readable and operational", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await page.getByRole("button", { name: "Explore sample audit" }).click();
  await expect(page.getByText("Sample audit", { exact: true }).first()).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
  await page.screenshot({ path: "../.tmp/mobile.png", fullPage: true });
});

test("a blocked audit reports insufficient coverage instead of a clean result", async ({ page, request }) => {
  const response = await request.post("http://127.0.0.1:8000/api/demo-audits", { data: {} });
  const sample = await response.json();
  const blocked = {
    ...sample, id: "blocked-ui-fixture", mode: "live", status: "failed", ai_status: "unavailable",
    pages: [{ ...sample.pages[0], outcome: "blocked", status_code: null, error: "robots.txt disallows this URL." }],
    issues: [], recommendations: [], score: { ...sample.score, value: null, assessed_pages: 0 },
    coverage: { attempted: 1, assessed: 0, blocked: 1, failed: 0, unchecked: 0, truncated: false },
    summary: "No pages could be assessed.", warnings: ["The website's crawl policy prevented access."],
  };
  await page.route("**/api/audits/blocked-ui-fixture", (route) => route.fulfill({ json: blocked }));
  await page.goto("/?audit=blocked-ui-fixture");
  await expect(page.getByRole("heading", { name: "No pages could be assessed." })).toBeVisible();
  await expect(page.getByText("The completed checks did not identify any findings on the assessed pages.")).toHaveCount(0);
});
