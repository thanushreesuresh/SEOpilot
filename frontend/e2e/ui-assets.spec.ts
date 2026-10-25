import { expect, test } from "@playwright/test";

for (const viewport of [{ name: "desktop", width: 1365, height: 900 }, { name: "mobile", width: 390, height: 844 }]) {
  test(`stylesheet delivery and hydrated navigation at ${viewport.name} size`, async ({ page }, testInfo) => {
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    page.on("console", (message) => { if (message.type() === "error") errors.push(message.text()); });
    page.on("response", (response) => {
      if (response.url().includes("/_next/static/") && response.status() >= 400) errors.push(`Asset HTTP ${response.status()}`);
    });
    await page.route("**/api/audits", (route) => route.fulfill({ json: [] }));
    await page.route("**/api/usage", (route) => route.fulfill({ json: {
      limit: 3, used: 0, remaining: 3, reset_at: null, retry_after: 0, window_hours: 24, ai_enabled: false, ai_calls_remaining: 20,
    } }));
    await page.setViewportSize(viewport);
    await page.goto("/");
    await expect(page).toHaveTitle("SEOPilot — Your next move in search");
    await expect(page.getByRole("heading", { name: "Your next move in search." })).toBeVisible();
    await expect(page.getByText("Loading your workspace…", { exact: true })).toHaveCount(0);
    await expect(page.locator("body")).toHaveCSS("margin", "0px");
    await expect(page.locator("body")).toHaveCSS("font-family", /Arial|Helvetica|sans-serif/);
    if (viewport.name === "desktop") await expect(page.locator(".sidebar")).toHaveCSS("position", "fixed");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    const stylesheets = page.locator('link[rel="stylesheet"]');
    expect(await stylesheets.count()).toBeGreaterThan(0);
    const stylesheet = await stylesheets.first().getAttribute("href");
    expect(stylesheet).toBeTruthy();
    const css = await page.request.get(stylesheet!);
    expect(css.ok()).toBe(true);
    expect(css.headers()["content-type"]).toContain("text/css");
    await testInfo.attach(`styled-${viewport.name}`, { body: await page.screenshot(), contentType: "image/png" });
    const history = page.getByRole("button", { name: "Audit history", exact: true });
    await history.focus();
    await page.keyboard.press("Enter");
    await expect(page.getByRole("heading", { name: "Audit history", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Back to overview", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Your next move in search." })).toBeVisible();
    expect(errors).toEqual([]);
  });
}
