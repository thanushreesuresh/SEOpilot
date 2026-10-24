import { expect, test, type Download, type Page } from "@playwright/test";
import type { Audit, AuditSummary } from "../src/lib/api";
import type { AuditComparison, AuditReport, FindingChange, ReportFormat } from "../src/lib/reporting-api";

// All API calls are intercepted. These cases exercise saved fixture data without
// crawling a website, creating an audit, or contacting an AI provider.
const BEFORE_ID = "11111111-1111-4111-8111-111111111111";
const AFTER_ID = "22222222-2222-4222-8222-222222222222";
const BLOCKED_ID = "33333333-3333-4333-8333-333333333333";
const OTHER_ORIGIN_ID = "44444444-4444-4444-8444-444444444444";
const LIVE_ID = "55555555-5555-4555-8555-555555555555";
const ACTIVE_ID = "66666666-6666-4666-8666-666666666666";
const ORIGIN = "https://reporting.example.com";
const ABOUT = `${ORIGIN}/about`;
const CONTACT = `${ORIGIN}/contact`;
const SERVICES = `${ORIGIN}/services`;
const BEFORE_DATE = "2026-10-25T02:00:00Z";
const AFTER_DATE = "2026-10-25T03:00:00Z";
const BLOCKED_DATE = "2026-10-25T04:00:00Z";
const CANARY = '<img data-reporting-canary src=x onerror="window.reportingCanary=true">';
const CONTEXT_MESSAGE = "Review JSON-LD context: a root object has no @context. Fully qualified IRIs may be intentional.";

function audit(id: string, date: string, blocked = false): Audit {
  return {
    id, url: ABOUT, origin: ORIGIN, mode: "demo", status: blocked ? "partial" : "completed",
    created_at: date, updated_at: date, completed_at: date, business_context: "", allow_ai: false,
    options: { page_limit: 15, max_depth: 2, delay_ms: 750, timeout_seconds: 10, response_bytes: 2097152, total_seconds: 120 },
    progress: { stage: "completed", visited: 3, discovered: 3, limit: 15, message: "Saved sample audit completed." },
    pages: [ABOUT, CONTACT, SERVICES].map((url, index) => ({
      id: `${id}-page-${index}`, url, depth: index ? 1 : 0, status_code: blocked && index === 1 ? null : 200,
      outcome: blocked && index === 1 ? "blocked" : "html", content_type: "text/html", title: `Saved page ${index + 1}`,
      description: "Saved sample page description.", headings: [{ level: 1, text: "Saved sample page" }],
      canonicals: [url], robots: [], images: [], links: [], text_excerpt: "Saved sample page text.",
      error: blocked && index === 1 ? "robots.txt disallows this URL." : null, truncated_fields: [],
      structured_data: index === 0 ? { blocks: 1, types: ["Organization"], observations: [{
        code: "json_ld_missing_context", message: CONTEXT_MESSAGE, block_index: 1, evidence: CANARY,
      }], truncated: false } : index === 1 ? null : { blocks: 0, types: [], observations: [], truncated: false },
    })),
    issues: [], recommendations: [], warnings: [],
    coverage: { attempted: 3, assessed: blocked ? 2 : 3, blocked: blocked ? 1 : 0, failed: 0, unchecked: 0, truncated: false },
    score: { version: "1", value: id === BEFORE_ID ? 80 : 85, assessed_pages: blocked ? 2 : 3, formula: "Saved fixture score." },
    ai_status: "demo", summary: "Saved sample results for reporting interface checks.", rules_version: "1", verification_urls: [],
  };
}

function finding(status: FindingChange["status"], title: string, url: string, reason: string): FindingChange {
  return { stable_id: `${status}:${url}`, rule_id: "page_title", url, field: "title", title, severity: "Medium", reason,
    is_site: false, before_issue_ids: status === "added" ? [] : ["before-finding"],
    after_issue_ids: status === "resolved" || status === "unresolved_unknown" ? [] : ["after-finding"],
    status, after_state: status === "unresolved_unknown" ? "blocked" : "assessed" };
}

function comparison(afterId: string, mismatch = false): AuditComparison {
  const blocked = afterId === BLOCKED_ID;
  const added = blocked || mismatch ? [] : [finding("added", "Contact title needs attention", CONTACT, "A finding is present in the later assessed page.")];
  const persistent = mismatch ? [] : [finding("persistent", "Services title is still short", SERVICES, "The same field still has a finding in both audits.")];
  const resolved = mismatch ? [] : [finding("resolved", "About title now passes the check", ABOUT, "The later assessed page passes this check.")];
  const unknown = blocked || mismatch ? [finding("unresolved_unknown", "Contact title remains unverified", CONTACT,
    mismatch ? "Rules versions differ, so the earlier finding cannot be confirmed as resolved." : "The later audit was blocked on this URL; no comparable follow-up evidence is available.")] : [];
  if (mismatch) unknown[0].after_state = "unknown";
  return {
    before_audit_id: BEFORE_ID, after_audit_id: afterId, origin: ORIGIN,
    rules_version_before: "1", rules_version_after: mismatch ? "2" : "1", score_version_before: "1", score_version_after: "1",
    versions_match: !mismatch, assessed_urls_before: [ABOUT, CONTACT, SERVICES],
    assessed_urls_after: blocked ? [ABOUT, SERVICES] : [ABOUT, CONTACT, SERVICES],
    common_assessed_urls: blocked ? [ABOUT, SERVICES] : [ABOUT, CONTACT, SERVICES], added_assessed_urls: [], removed_assessed_urls: blocked ? [CONTACT] : [],
    coverage_before: audit(BEFORE_ID, BEFORE_DATE).coverage, coverage_after: audit(afterId, AFTER_DATE, blocked).coverage,
    coverage_comparable: !blocked, score_before: 80, score_after: 85, score_delta: blocked || mismatch ? null : 5,
    score_delta_reason: mismatch ? "Rules or score versions differ; score change is unavailable." : blocked ? "Assessed coverage differs; score change is unavailable." : "Matching versions and assessed coverage allow a technical score comparison.",
    added, persistent, resolved, unresolved_unknown: unknown,
    counts: { added: added.length, persistent: persistent.length, resolved: resolved.length, unresolved_unknown: unknown.length },
    limitations: ["Saved findings cover assessed pages only; excluded pages cannot establish a fix."],
  };
}

function report(format: ReportFormat): AuditReport {
  const extension = format === "markdown" ? "md" : format;
  const content = format === "markdown" ? "# Saved sample audit\n\nNo new crawl or AI calls.\n" : format === "csv" ? 'kind,title\n"finding","Saved sample finding"\n' : JSON.stringify({ audit_id: AFTER_ID, mode: "demo", saved: true });
  return { filename: `seopilot-${AFTER_ID}.${extension}`, media_type: format === "markdown" ? "text/markdown" : format === "csv" ? "text/csv" : "application/json", content };
}

type MockState = {
  audits: Record<string, Audit>; reportFailure: boolean; comparisonFailure: boolean; mismatch: boolean;
  requests: { method: string; path: string; body: unknown }[]; unexpected: string[];
};

async function mockReporting(page: Page) {
  const state: MockState = { audits: { [BEFORE_ID]: audit(BEFORE_ID, BEFORE_DATE), [AFTER_ID]: audit(AFTER_ID, AFTER_DATE),
    [BLOCKED_ID]: audit(BLOCKED_ID, BLOCKED_DATE, true) }, reportFailure: false, comparisonFailure: false, mismatch: false, requests: [], unexpected: [] };
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const method = request.method();
    const body: unknown = method === "GET" ? null : request.postDataJSON();
    state.requests.push({ method, path, body });
    const fulfill = (json: unknown, status = 200) => route.fulfill({ status, json });
    if (path === "/api/usage" && method === "GET") return fulfill({ limit: 3, used: 0, remaining: 3, reset_at: null,
      retry_after: 0, window_hours: 24, ai_enabled: false, ai_calls_remaining: 20 });
    if (path === "/api/audits" && method === "GET") {
      const history: AuditSummary[] = Object.values(state.audits).map((item) => ({ id: item.id, url: item.url, mode: item.mode,
        status: item.status, created_at: item.created_at, score: item.score.value, pages: item.pages.length, issues: item.issues.length }));
      history.push({ ...history[1], id: OTHER_ORIGIN_ID, url: "https://other.example.com/about" },
        { ...history[1], id: LIVE_ID, mode: "live" }, { ...history[1], id: ACTIVE_ID, status: "crawling" });
      return fulfill(history);
    }
    const reportMatch = /^\/api\/audits\/([^/]+)\/report\/(markdown|csv|json)$/.exec(path);
    if (reportMatch && method === "GET") {
      if (state.reportFailure) return fulfill({ detail: "Report export temporarily unavailable. Try again." }, 503);
      return fulfill(report(reportMatch[2] as ReportFormat));
    }
    if (path === "/api/audit-comparisons" && method === "POST") {
      if (state.comparisonFailure) return fulfill({ detail: "Saved comparison temporarily unavailable. Try again." }, 503);
      const selected = body as { before_audit_id: string; after_audit_id: string };
      const result = comparison(selected.after_audit_id, state.mismatch);
      if ([selected.before_audit_id, selected.after_audit_id].some((id) => state.audits[id]?.pages.some(
        (item) => item.truncated_fields.length || item.structured_data?.truncated,
      ))) {
        result.coverage_comparable = false;
        result.score_delta = null;
        result.score_delta_reason = "Score delta withheld because retained page evidence is truncated.";
      }
      return fulfill(result);
    }
    const auditMatch = /^\/api\/audits\/([^/]+)$/.exec(path);
    if (auditMatch && state.audits[auditMatch[1]] && method === "GET") return fulfill(state.audits[auditMatch[1]]);
    if (/^\/api\/audits\/[^/]+\/dispositions$/.test(path) && method === "GET") return fulfill([]);
    state.unexpected.push(`${method} ${path}`);
    return fulfill({ detail: "Unexpected request in the isolated reporting fixture." }, 500);
  });
  return state;
}

async function openComparison(page: Page) {
  await page.goto(`/?audit=${AFTER_ID}`);
  await expect(page.getByRole("heading", { name: "Audit overview", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Audit history", exact: true }).click();
  await page.getByRole("button", { name: "Compare audits", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Compare audits", exact: true })).toBeVisible();
}

async function readDownload(download: Download): Promise<string> {
  const stream = await download.createReadStream();
  expect(stream).not.toBeNull();
  let text = "";
  for await (const chunk of stream!) text += chunk.toString();
  return text;
}

test("saved reports download Markdown, CSV and JSON with exact filenames and content", async ({ page }) => {
  const state = await mockReporting(page);
  await page.goto(`/?audit=${AFTER_ID}`);
  const exportButton = page.getByRole("button", { name: "Download report", exact: true });
  await expect(exportButton).toBeEnabled();
  expect(state.requests.filter((request) => request.path.includes("/report/"))).toEqual([]);
  for (const format of ["markdown", "csv", "json"] as const) {
    await page.getByRole("combobox", { name: "Report format", exact: true }).selectOption(format);
    const downloaded = page.waitForEvent("download");
    await exportButton.click();
    const download = await downloaded;
    expect(download.suggestedFilename()).toBe(report(format).filename);
    expect(await readDownload(download)).toBe(report(format).content);
    await expect(page.getByRole("status").filter({ hasText: `Report prepared: ${report(format).filename}` })).toBeVisible();
  }
  expect(state.requests.filter((request) => request.path.includes("/report/")).map((request) => request.method)).toEqual(["GET", "GET", "GET"]);
  expect(state.requests.filter((request) => request.method !== "GET")).toEqual([]);
  expect(state.unexpected).toEqual([]);
});

test("report failures can be retried and unfinished audits cannot be exported", async ({ page }) => {
  const state = await mockReporting(page);
  state.reportFailure = true;
  await page.goto(`/?audit=${AFTER_ID}`);
  const button = page.getByRole("button", { name: "Download report", exact: true });
  await button.click();
  await expect(page.getByRole("alert").filter({ hasText: "Report export temporarily unavailable. Try again." })).toBeVisible();
  await expect(button).toBeEnabled();
  state.reportFailure = false;
  const downloaded = page.waitForEvent("download");
  await button.click();
  expect((await downloaded).suggestedFilename()).toBe(report("markdown").filename);
  await expect(page.getByRole("alert").filter({ hasText: "Report export temporarily unavailable. Try again." })).toHaveCount(0);
  state.audits[AFTER_ID] = { ...state.audits[AFTER_ID], status: "crawling", completed_at: null };
  await page.reload();
  await expect(button).toBeDisabled();
  await expect(page.getByRole("combobox", { name: "Report format", exact: true })).toBeDisabled();
  await expect(page.getByText("Reports are available when this audit finishes.", { exact: true })).toBeVisible();
  expect(state.requests.filter((request) => request.path.includes("/report/"))).toHaveLength(2);
  expect(state.requests.filter((request) => request.method !== "GET")).toEqual([]);
  expect(state.unexpected).toEqual([]);
});

test("comparison selection enforces origin, mode and chronology before a click-only request", async ({ page }) => {
  const state = await mockReporting(page);
  await openComparison(page);
  const earlier = page.getByRole("combobox", { name: "Earlier audit", exact: true });
  const later = page.getByRole("combobox", { name: "Later audit", exact: true });
  await expect(earlier.locator(`option[value="${ACTIVE_ID}"]`)).toHaveCount(0);
  await earlier.selectOption(BEFORE_ID);
  for (const excluded of [BEFORE_ID, OTHER_ORIGIN_ID, LIVE_ID, ACTIVE_ID]) await expect(later.locator(`option[value="${excluded}"]`)).toHaveCount(0);
  await earlier.selectOption(BLOCKED_ID);
  await expect(later).toBeDisabled();
  await expect(page.getByRole("button", { name: "Run comparison", exact: true })).toBeDisabled();
  await earlier.selectOption(BEFORE_ID);
  await later.selectOption(AFTER_ID);
  expect(state.requests.filter((request) => request.method !== "GET")).toEqual([]);
  await page.getByRole("button", { name: "Run comparison", exact: true }).click();
  await expect(page.getByText("Sample comparison", { exact: true })).toBeVisible();
  await expect(page.getByText("+5 points", { exact: true })).toBeVisible();
  await expect(page.getByText(/These results compare saved sample data/)).toBeVisible();
  expect(state.requests.filter((request) => request.method === "POST")).toEqual([{ method: "POST", path: "/api/audit-comparisons", body: { before_audit_id: BEFORE_ID, after_audit_id: AFTER_ID } }]);
  expect(state.unexpected).toEqual([]);
});

test("blocked follow-up coverage stays unknown, hides score delta and supports finding filters", async ({ page }) => {
  const state = await mockReporting(page);
  await openComparison(page);
  await page.getByRole("combobox", { name: "Earlier audit", exact: true }).selectOption(BEFORE_ID);
  await page.getByRole("combobox", { name: "Later audit", exact: true }).selectOption(BLOCKED_ID);
  await page.getByRole("button", { name: "Run comparison", exact: true }).click();
  await expect(page.getByText("Unavailable", { exact: true })).toBeVisible();
  await expect(page.getByText("Assessed coverage differs; score change is unavailable.", { exact: false })).toBeVisible();
  await page.getByRole("combobox", { name: "Change status", exact: true }).selectOption("unresolved_unknown");
  const unknown = page.getByRole("row").filter({ hasText: "Contact title remains unverified" });
  await expect(unknown).toContainText("Unresolved / unknown");
  await expect(unknown).toContainText("Later evidence: blocked");
  await expect(page.getByRole("row").filter({ hasText: "About title now passes the check" })).toHaveCount(0);
  await page.getByRole("searchbox", { name: "Filter comparison URLs", exact: true }).fill("missing-path");
  await expect(page.getByRole("status").filter({ hasText: "No finding changes match these filters." })).toBeVisible();
  await page.getByRole("searchbox", { name: "Filter comparison URLs", exact: true }).fill("/contact");
  await expect(unknown).toBeVisible();
  await page.getByText("Coverage, versions, and excluded pages", { exact: true }).click();
  await expect(page.getByText("Versions match. Assessed page coverage is not comparable.", { exact: true })).toBeVisible();
  await page.getByText("Removed from assessed coverage (1)", { exact: true }).click();
  await expect(page.getByRole("link", { name: CONTACT, exact: true })).toHaveCount(2);
  expect(state.unexpected).toEqual([]);
});

test("version mismatch discloses check versions without implying a comparable score change", async ({ page }) => {
  const state = await mockReporting(page);
  state.mismatch = true;
  await openComparison(page);
  await page.getByRole("combobox", { name: "Later audit", exact: true }).selectOption(AFTER_ID);
  await page.getByRole("button", { name: "Run comparison", exact: true }).click();
  await expect(page.getByText("Unavailable", { exact: true })).toBeVisible();
  await expect(page.getByText("+5 points", { exact: true })).toHaveCount(0);
  await expect(page.getByText(/Rules or score versions differ; score change is unavailable/)).toBeVisible();
  await page.getByText("Coverage, versions, and excluded pages", { exact: true }).click();
  await expect(page.getByText("Versions differ. Assessed page coverage is comparable.", { exact: true })).toBeVisible();
  const versions = page.getByRole("table", { name: "Audit coverage and check versions", exact: true });
  await expect(versions.getByRole("row").filter({ hasText: "Rules version" }).getByRole("cell")).toHaveText(["1", "2"]);
  await expect(versions.getByRole("row").filter({ hasText: "Score version" }).getByRole("cell")).toHaveText(["1", "1"]);
  expect(state.unexpected).toEqual([]);
});

test("comparison service errors remain actionable and a retry replaces the error with saved results", async ({ page }) => {
  const state = await mockReporting(page);
  state.comparisonFailure = true;
  await openComparison(page);
  await page.getByRole("combobox", { name: "Later audit", exact: true }).selectOption(AFTER_ID);
  const button = page.getByRole("button", { name: "Run comparison", exact: true });
  await button.click();
  const alert = page.getByRole("alert").filter({ hasText: "Saved comparison temporarily unavailable. Try again." });
  await expect(alert).toBeVisible();
  await expect(button).toBeEnabled();
  await expect(page.getByText("Sample comparison", { exact: true })).toHaveCount(0);
  state.comparisonFailure = false;
  await button.click();
  await expect(page.getByText("Sample comparison", { exact: true })).toBeVisible();
  await expect(alert).toHaveCount(0);
  expect(state.requests.filter((request) => request.method === "POST").map((request) => request.path)).toEqual(["/api/audit-comparisons", "/api/audit-comparisons"]);
  expect(state.unexpected).toEqual([]);
});

test("clipped HTML keeps JSON-LD presence unknown", async ({ page }) => {
  const state = await mockReporting(page);
  state.audits[AFTER_ID].pages[2].structured_data = { blocks: 0, types: [], observations: [], truncated: true };
  await page.goto(`/?audit=${AFTER_ID}`);
  await page.getByRole("tab", { name: "Pages", exact: true }).click();
  await expect(page.getByText("JSON-LD inspection incomplete. Presence and syntax remain unknown.", { exact: true })).toBeVisible();
  await expect(page.getByText("No JSON-LD blocks detected.", { exact: true })).toHaveCount(0);
  expect(state.unexpected).toEqual([]);
});

test("mobile keyboard flows expose bounded JSON-LD evidence and keep comparison tables inside the viewport", async ({ page }, testInfo) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const state = await mockReporting(page);
  state.audits[AFTER_ID].pages[0].structured_data!.truncated = true;
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`/?audit=${AFTER_ID}`);
  await page.getByRole("tab", { name: "Issues", exact: true }).focus();
  await page.keyboard.press("End");
  await expect(page.getByRole("tab", { name: "Pages", exact: true })).toHaveAttribute("aria-selected", "true");
  const summary = page.getByText("JSON-LD · 1 block · Organization", { exact: true });
  await summary.focus(); await page.keyboard.press("Enter");
  await expect(page.getByText(`Block 1: ${CONTEXT_MESSAGE}`, { exact: true })).toBeVisible();
  await expect(page.getByText(CANARY, { exact: true })).toBeVisible();
  await expect(page.locator("[data-reporting-canary]")).toHaveCount(0);
  expect(await page.evaluate(() => Object.hasOwn(window, "reportingCanary"))).toBe(false);
  await expect(page.getByText("JSON-LD inspection reached a limit. This summary covers retained evidence only.", { exact: true })).toBeVisible();
  await expect(page.getByText("Checks cover supported JSON-LD structure and fields. Rich result eligibility is not established.", { exact: true })).toBeVisible();
  await expect(page.getByText("JSON-LD not assessed in this saved page.", { exact: true })).toBeVisible();
  await expect(page.getByText("No JSON-LD blocks detected.", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Audit history", exact: true }).focus(); await page.keyboard.press("Enter");
  await page.getByRole("button", { name: "Compare audits", exact: true }).focus(); await page.keyboard.press("Enter");
  await page.getByRole("combobox", { name: "Later audit", exact: true }).selectOption(AFTER_ID);
  await page.getByRole("button", { name: "Run comparison", exact: true }).focus(); await page.keyboard.press("Enter");
  await expect(page.getByText("Unavailable", { exact: true })).toBeVisible();
  const overflow = await page.evaluate(() => ({
    viewport: window.innerWidth, document: document.documentElement.scrollWidth,
    elements: [...document.querySelectorAll("body *")].flatMap((element) => {
      const box = element.getBoundingClientRect();
      return box.width && (box.right > window.innerWidth + 1 || box.left < -1)
        ? [{ tag: element.tagName, class: element.className, left: box.left, right: box.right }] : [];
    }).slice(0, 30),
  }));
  await page.screenshot({ path: testInfo.outputPath("reporting-mobile-before-coverage.png"), fullPage: true });
  expect(overflow.document, JSON.stringify(overflow)).toBeLessThanOrEqual(overflow.viewport + 1);
  await page.getByText("Coverage, versions, and excluded pages", { exact: true }).focus(); await page.keyboard.press("Enter");
  await expect(page.getByRole("table", { name: "Audit coverage and check versions", exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("reporting-mobile.png"), fullPage: true });
  expect(errors).toEqual([]);
  expect(state.unexpected).toEqual([]);
});
