import { expect, test } from "@playwright/test";
import { sampleAudit } from "./fixtures";

for (const viewport of [{ width: 1365, height: 900 }, { width: 390, height: 844 }]) {
  test(`failed crawl explains unknown SEO results at width ${viewport.width}`, async ({ page, request }) => {
    const sample = await sampleAudit(request);
    const failed = {
      ...sample, mode: "live", status: "failed", ai_status: "unavailable",
      summary: "Analyzed 0 pages; found 0 verified findings. Prioritize availability.",
      issues: [], recommendations: [],
      score: { ...sample.score, value: null, assessed_pages: 0, breakdown: null },
      coverage: { attempted: 1, assessed: 0, blocked: 1, failed: 0, unchecked: 0, truncated: false },
      pages: [{ ...sample.pages[0], outcome: "blocked", status_code: null, title: "", description: "",
        error: "Only public website addresses can be audited." }],
    };
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.route(`**/api/audits/${sample.id}`, (route) => route.fulfill({ json: failed }));
    await page.setViewportSize(viewport);
    await page.goto(`/?audit=${sample.id}`);
    await expect(page).toHaveTitle(/SEOPilot/);
    await expect(page.getByText("No pages could be assessed. SEO findings and score are unknown.", { exact: true })).toBeVisible();
    await expect(page.getByText(failed.summary, { exact: true })).toHaveCount(0);
    await expect(page.getByText("Only public website addresses can be audited.", { exact: true }).first()).toBeVisible();
    const inspect = page.getByRole("button", { name: "Inspect failed pages", exact: true });
    await inspect.focus();
    await page.keyboard.press("Enter");
    await expect(page.getByRole("tab", { name: "Pages", exact: true })).toHaveAttribute("aria-selected", "true");
    await expect(page.getByRole("button", { name: "Download report", exact: true })).toBeEnabled();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    expect(errors).toEqual([]);
  });
}
