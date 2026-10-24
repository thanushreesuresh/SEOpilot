import { expect, test, type Page } from "@playwright/test";
import type { Audit, AuditSummary } from "../src/lib/api";
import type { ConnectionStatus, FixRun, Project } from "../src/lib/fix-api";

// Every API call is intercepted. These browser cases never spend provider quota
// or connect to GitHub, and the hosted runner uses its own disposable database.
const PROJECT_ID = "11111111-1111-4111-8111-111111111111";
const AUDIT_ID = "22222222-2222-4222-8222-222222222222";
const RUN_ID = "33333333-3333-4333-8333-333333333333";
const PAGE_ID = "44444444-4444-4444-8444-444444444444";
const RECOMMENDATION_ID = "55555555-5555-4555-8555-555555555555";
const HASH = "a".repeat(64);
const DATE = "2026-10-25T02:00:00Z";
const ORIGIN = "https://owned.example.com";
const URL = `${ORIGIN}/about`;
const TITLE = "About Café Works — useful local services";
const DESCRIPTION = "Discover useful local services and learn how the Café Works team can help your next project.";
const PATCH = `--- a/frontend/app/about/page.tsx\n+++ b/frontend/app/about/page.tsx\n@@ -1,2 +1,2 @@\n-export const metadata = { title: "About" };\n+export const metadata = { title: ${JSON.stringify(TITLE)} };\n // <img data-seopilot-canary src=x onerror="window.seopilotCanary=true">\n`;

function project(): Project {
  return { id: PROJECT_ID, name: "Owned pilot", production_origin: ORIGIN, installation_id: 1234,
    repository_id: 5678, repository_owner: "owner", repository_name: "pilot", base_branch: "main",
    app_subdirectory: "frontend", workflow: "seopilot-validation.yml", connected: true, confirmed_at: DATE };
}

function audit(): Audit {
  return { id: AUDIT_ID, url: URL, origin: ORIGIN, mode: "live", status: "completed", created_at: DATE,
    updated_at: DATE, completed_at: DATE, business_context: "", allow_ai: false,
    options: { page_limit: 15, max_depth: 2, delay_ms: 750, timeout_seconds: 10, response_bytes: 2097152, total_seconds: 120 },
    progress: { stage: "completed", visited: 1, discovered: 1, limit: 15, message: "Audit completed." },
    pages: [{ id: PAGE_ID, url: URL, depth: 0, status_code: 200, outcome: "html", content_type: "text/html",
      title: "About", description: DESCRIPTION, headings: [{ level: 1, text: "About Café Works" }],
      canonicals: [URL], robots: ["robots: index, follow"], images: [], links: [],
      text_excerpt: DESCRIPTION, error: null, truncated_fields: [] }], issues: [],
    recommendations: [{ id: RECOMMENDATION_ID, source: "rule", kind: "title", title: "Clarify the page title",
      url: URL, page_id: PAGE_ID, issue_ids: [], evidence_ids: [], rationale: "Reviewed title wording.",
      suggested_value: TITLE, priority: "Medium", status: "approved", decided_at: DATE, basis: "observed" }],
    warnings: [], coverage: { attempted: 1, assessed: 1, blocked: 0, failed: 0, unchecked: 0, truncated: false },
    score: { version: "1", value: 90, assessed_pages: 1, formula: "Documented deterministic score." },
    ai_status: "unavailable", summary: "One page assessed.", rules_version: "1", verification_urls: [] };
}

function fixRun(status: FixRun["status"] = "proposed"): FixRun {
  return { id: RUN_ID, project_id: PROJECT_ID, audit_id: AUDIT_ID, repository_id: 5678, base_branch: "main",
    base_sha: "b".repeat(40), patch_hash: HASH, created_at: DATE, updated_at: DATE,
    expires_at: "2026-10-26T02:00:00Z", status, targets: [{ url: URL, route: "/about", path: "frontend/app/about/page.tsx",
      old_title: "About", old_description: DESCRIPTION, title: TITLE, description: DESCRIPTION,
      canonical: [URL], robots: ["robots: index, follow"] }], changed_files: ["frontend/app/about/page.tsx"],
    changed_lines: 2, branch: `seopilot/${RUN_ID}`, head_sha: null, pr_number: null, pr_url: null,
    message: "Review the exact diff. Patch generation used zero AI calls.",
    validation: { status: "pending", summary: "Validation has not completed.", run_url: null, details: {} },
    verification: {}, verification_audit_id: null, source_purged: false, poll_until: "2099-01-01T00:00:00Z" };
}

type MockState = {
  configured: boolean; projects: Project[]; run: FixRun | null; patchHash: string;
  connectionFailure: boolean; requests: { method: string; path: string; body: unknown }[];
};

async function mockWorkspace(page: Page, options: Partial<MockState> = {}) {
  const state: MockState = { configured: true, projects: [project()], run: null, patchHash: HASH,
    connectionFailure: false, requests: [], ...options };
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const pathname = new globalThis.URL(request.url()).pathname;
    const method = request.method();
    const body: unknown = method === "GET" ? null : request.postDataJSON();
    state.requests.push({ method, path: pathname, body });
    const fulfill = (json: unknown, status = 200) => route.fulfill({ status, json });
    if (pathname === "/api/usage") return fulfill({ limit: 3, used: 0, remaining: 3, reset_at: null,
      retry_after: 0, window_hours: 24, ai_enabled: false, ai_calls_remaining: 20 });
    if (pathname === "/api/audits" && method === "GET") {
      const history: AuditSummary[] = [{ id: AUDIT_ID, url: URL, mode: "live", status: "completed", created_at: DATE,
        score: 90, pages: 1, issues: 0 }];
      return fulfill(history);
    }
    if (pathname === `/api/audits/${AUDIT_ID}`) return fulfill(audit());
    if (pathname === "/api/github/connection") {
      if (state.connectionFailure) return fulfill({ detail: "GitHub connection is unavailable. Check local setup." }, 503);
      const connection: ConnectionStatus = { configured: state.configured,
        message: state.configured ? "Selected repositories verified." : "Configure the private GitHub App on this machine.",
        repositories: state.configured ? [{ id: 5678, installation_id: 1234, owner: "owner", name: "pilot", default_branch: "main" }] : [],
        publication_limit: 2, publications_remaining: 2, actions_notice: "GitHub Actions usage is separate from OpenAI usage." };
      return fulfill(connection);
    }
    if (pathname === "/api/projects") {
      if (method === "POST") { state.projects = [project()]; return fulfill(project(), 201); }
      return fulfill(state.projects);
    }
    if (pathname === `/api/projects/${PROJECT_ID}/disconnect`) {
      state.projects = [{ ...project(), connected: false }];
      return fulfill(state.projects[0]);
    }
    if (pathname === "/api/fix-runs") {
      if (method === "POST") { state.run = fixRun(); return fulfill(state.run, 202); }
      return fulfill(state.run ? [state.run] : []);
    }
    if (pathname === `/api/fix-runs/${RUN_ID}/patch`) return fulfill({ filename: `seopilot-${RUN_ID}.patch`, patch: PATCH, patch_hash: state.patchHash });
    if (pathname === `/api/fix-runs/${RUN_ID}/refresh` && state.run) return fulfill(state.run, 202);
    if (pathname === `/api/fix-runs/${RUN_ID}/publish`) {
      state.run = { ...fixRun("pr_opened"), head_sha: "c".repeat(40), pr_number: 9,
        pr_url: "https://github.com/owner/pilot/pull/9", message: "Draft PR opened. Manual review, merge and deployment are required." };
      return fulfill(state.run, 202);
    }
    if (pathname === `/api/fix-runs/${RUN_ID}/verify`) {
      state.run = { ...fixRun("verification_failed"), pr_number: 9, pr_url: "https://github.com/owner/pilot/pull/9",
        message: "Live verification did not pass. A recorded page was blocked.",
        verification: { status: "failed", checks: [{ url: URL, passed: false, outcome: "blocked" }],
          coverage: { attempted: 1, assessed: 0, blocked: 1, failed: 0, unchecked: 0, truncated: false },
          score_comparable: false, before_score: 90, after_score: null } };
      return fulfill(state.run, 202);
    }
    if (pathname === `/api/fix-runs/${RUN_ID}/delete-source`) {
      state.run = { ...fixRun("cancelled"), source_purged: true, message: "Private patch deleted." };
      return fulfill(state.run);
    }
    if (pathname === `/api/fix-runs/${RUN_ID}` && state.run) return fulfill(state.run);
    throw new Error(`Unmocked API request: ${method} ${pathname}`);
  });
  return state;
}

async function openProjects(page: Page) {
  await page.goto("/");
  await page.getByRole("button", { name: "Projects & fixes", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Review. Publish. Verify." })).toBeVisible();
}

test("missing GitHub App explains setup and disables project writes", async ({ page }) => {
  const state = await mockWorkspace(page, { configured: false, projects: [] });
  await openProjects(page);
  await expect(page.getByRole("heading", { name: "Connect your GitHub App" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Connect a project", exact: true })).toBeDisabled();
  await expect(page.getByRole("link", { name: "Setup guide" })).toHaveAttribute("href", /github-app-setup/);
  await expect(page.getByText(/Private source stays outside OpenAI requests/)).toBeVisible();
  expect(state.requests.filter((request) => request.method !== "GET")).toEqual([]);
});

test("onboarding requires ownership and sends installed repository identity", async ({ page }) => {
  const state = await mockWorkspace(page, { projects: [] });
  await openProjects(page);
  await page.getByRole("button", { name: "Connect a project", exact: true }).click();
  await page.getByRole("textbox", { name: "Project name", exact: true }).fill("Owned pilot");
  await page.getByRole("textbox", { name: "Production origin", exact: true }).fill(ORIGIN);
  await expect(page.getByRole("combobox", { name: "Installed repository", exact: true })).toHaveValue("5678");
  await page.getByRole("textbox", { name: "Application subdirectory", exact: true }).fill("frontend");
  await page.getByRole("button", { name: "Confirm project mapping", exact: true }).click();
  expect(state.requests.filter((request) => request.method === "POST")).toEqual([]);
  const ownership = page.getByRole("checkbox", { name: /I own this website and confirm/ });
  await ownership.focus(); await page.keyboard.press("Space");
  await expect(ownership).toBeChecked();
  await page.getByRole("button", { name: "Confirm project mapping", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Your projects", exact: true })).toBeVisible();
  expect(state.requests.find((request) => request.path === "/api/projects" && request.method === "POST")?.body)
    .toEqual({ name: "Owned pilot", production_origin: ORIGIN, repository_id: 5678, installation_id: 1234,
      base_branch: "main", app_subdirectory: "frontend", workflow: "seopilot-validation.yml", confirms_ownership: true });
});

test("approved text prepares a private proposal and escaped diff without publishing", async ({ page }) => {
  const state = await mockWorkspace(page);
  await openProjects(page);
  await page.getByRole("combobox", { name: "Completed live audit", exact: true }).selectOption(AUDIT_ID);
  await page.getByRole("checkbox", { name: "/about", exact: true }).check();
  await expect(page.getByRole("textbox", { name: /Page title/ })).toHaveValue(TITLE);
  await page.getByRole("textbox", { name: /Meta description/ }).fill(DESCRIPTION);
  await page.getByRole("button", { name: "Prepare patch for review", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Proposed metadata changes", exact: true })).toBeVisible();
  expect(state.requests.find((request) => request.path === "/api/fix-runs" && request.method === "POST")?.body)
    .toEqual({ project_id: PROJECT_ID, audit_id: AUDIT_ID, edits: [{ url: URL, title: TITLE,
      description: DESCRIPTION, recommendation_ids: [RECOMMENDATION_ID] }] });
  await expect(page.getByRole("button", { name: "Create draft PR", exact: true })).toBeDisabled();
  await page.getByRole("button", { name: "Inspect exact diff", exact: true }).click();
  await expect(page.getByLabel("Proposed code diff", { exact: true })).toHaveText(PATCH);
  await expect(page.locator("[data-seopilot-canary]")).toHaveCount(0);
  expect(await page.evaluate(() => Object.hasOwn(window, "seopilotCanary"))).toBe(false);
  expect(state.requests.filter((request) => request.path.endsWith("/publish"))).toEqual([]);
});

test("draft publication needs inspected diff and a separate keyboard-approved consent", async ({ page }) => {
  const state = await mockWorkspace(page, { run: fixRun() });
  await openProjects(page);
  const publish = page.getByRole("button", { name: "Create draft PR", exact: true });
  const consent = page.getByRole("checkbox", { name: /I reviewed this exact patch/ });
  await expect(consent).toBeDisabled(); await expect(publish).toBeDisabled();
  await page.getByRole("button", { name: "Inspect exact diff", exact: true }).click();
  await expect(consent).toBeEnabled(); await expect(publish).toBeDisabled();
  await consent.focus(); await page.keyboard.press("Space");
  await expect(publish).toBeEnabled();
  await publish.click();
  await expect(page.getByRole("link", { name: "Open pull request", exact: true })).toHaveAttribute("href", "https://github.com/owner/pilot/pull/9");
  expect(state.requests.filter((request) => request.path.endsWith("/publish"))).toHaveLength(1);
  expect(state.requests.find((request) => request.path.endsWith("/publish"))?.body)
    .toEqual({ patch_hash: HASH, confirms_publication: true });
  await expect(page.getByText(/Manual review, merge and deployment are required/)).toBeVisible();
});

test("a mismatched patch hash cannot unlock publication", async ({ page }) => {
  const state = await mockWorkspace(page, { run: fixRun(), patchHash: "d".repeat(64) });
  await openProjects(page);
  await page.getByRole("button", { name: "Inspect exact diff", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("This patch no longer matches the proposal.");
  await expect(page.getByRole("checkbox", { name: /I reviewed this exact patch/ })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Create draft PR", exact: true })).toBeDisabled();
  expect(state.requests.filter((request) => request.path.endsWith("/publish"))).toEqual([]);
});

test("CI failure and missing evidence remain visible in fix history", async ({ page }) => {
  const run = fixRun("checks_failed");
  run.validation = { status: "missing", summary: "The matching bounded validation artifact is missing or ambiguous.",
    run_url: "https://github.com/owner/pilot/actions/runs/123", details: {} };
  await mockWorkspace(page, { run });
  await openProjects(page);
  await expect(page.getByRole("heading", { name: "GitHub-hosted validation · missing", exact: true })).toBeVisible();
  await expect(page.getByText("The matching bounded validation artifact is missing or ambiguous.")).toBeVisible();
  await expect(page.getByRole("link", { name: "Open validation run" })).toHaveAttribute("href", /actions\/runs\/123$/);
  await expect(page.getByRole("listitem").filter({ hasText: "Live verified" })).not.toHaveAttribute("aria-current", "step");
});

test("deployment acknowledgement starts no-AI verification and blocked coverage stays failed", async ({ page }) => {
  const state = await mockWorkspace(page, { run: fixRun("awaiting_deployment") });
  await openProjects(page);
  const verify = page.getByRole("button", { name: "Verify live", exact: true });
  await expect(verify).toBeDisabled();
  await expect(page.getByText(/uses the existing daily audit allowance/)).toBeVisible();
  await page.getByRole("checkbox", { name: /I deployed the merged change/ }).check();
  await verify.click();
  const results = page.getByRole("region", { name: "Live verification results", exact: true });
  await expect(results).toContainText('"status": "failed"');
  await expect(results).toContainText('"outcome": "blocked"');
  await expect(results).toContainText('"score_comparable": false');
  await expect(results).toContainText("Reduced coverage never becomes a clean verification.");
  await expect(page.getByRole("listitem").filter({ hasText: "Live verified" })).not.toHaveAttribute("aria-current", "step");
  expect(state.requests.filter((request) => request.path.endsWith("/verify"))).toHaveLength(1);
});

test("mobile keyboard review supports patch download and immediate source deletion", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mockWorkspace(page, { run: fixRun() });
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  const navigation = page.getByRole("button", { name: "Projects & fixes", exact: true });
  await navigation.focus(); await page.keyboard.press("Enter");
  await page.getByRole("button", { name: "Inspect exact diff", exact: true }).click();
  const diff = page.getByLabel("Proposed code diff", { exact: true });
  await diff.focus(); await expect(diff).toBeFocused();
  const downloadEvent = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download patch", exact: true }).click();
  expect((await downloadEvent).suggestedFilename()).toBe(`seopilot-${RUN_ID}.patch`);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("v2-mobile-review.png"), fullPage: true });
  await page.getByText("Cancel or delete private source", { exact: true }).click();
  await page.getByRole("button", { name: "Delete retained source now", exact: true }).click();
  await expect(page.getByText(/Retained source and patches were deleted/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Download patch", exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Create draft PR", exact: true })).toHaveCount(0);
  expect(errors).toEqual([]);
});

test("connection failures show a retryable error without enabling writes", async ({ page }) => {
  const state = await mockWorkspace(page, { projects: [], connectionFailure: true });
  await openProjects(page);
  await expect(page.getByRole("alert")).toContainText("GitHub connection is unavailable. Check local setup.");
  await expect(page.getByRole("button", { name: "Connect a project", exact: true })).toBeDisabled();
  state.connectionFailure = false;
  await page.getByRole("button", { name: "Refresh connection", exact: true }).click();
  await expect(page.getByRole("heading", { name: "GitHub App configured", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Connect a project", exact: true })).toBeEnabled();
});
