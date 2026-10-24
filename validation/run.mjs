// Runs only in the owner's disposable GitHub-hosted validation job.
import fs from "node:fs/promises";
import path from "node:path";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import { appDirectory, pageChecks, readManifest } from "./lib.mjs";

const MAX_REPORT = 128 * 1024;
const MAX_SCREENSHOT = 2 * 1024 * 1024;
const workflowDeadline = Date.now() + 410000;
const statuses = ["install", "build", "render", "lint", "typecheck", "test"];
const checks = statuses.map((name) => ({ name, status: ["lint", "typecheck", "test"].includes(name) ? "skipped" : "failed" }));
const check = (name, status) => { checks.find((item) => item.name === name).status = status; };

function childEnvironment() {
  // No GitHub token, repository secrets, OpenAI credentials or App key is inherited.
  return { PATH: process.env.PATH, HOME: process.env.HOME, TMPDIR: process.env.RUNNER_TEMP ?? "/tmp", CI: "true",
    NEXT_TELEMETRY_DISABLED: "1", FORCE_COLOR: "0", npm_config_audit: "false", npm_config_fund: "false" };
}

async function terminate(child) {
  if (!child || child.exitCode !== null) return;
  try { process.kill(-child.pid, "SIGTERM"); } catch { child.kill("SIGTERM"); }
  await new Promise((resolve) => setTimeout(resolve, 250));
  try { process.kill(-child.pid, "SIGKILL"); } catch { child.kill("SIGKILL"); }
}

async function command(args, cwd, milliseconds) {
  if (Date.now() >= workflowDeadline) return false;
  const child = spawn("npm", args, { cwd, env: childEnvironment(), stdio: "ignore", detached: true, shell: false });
  let timer;
  const finished = new Promise((resolve) => {
    child.once("error", () => resolve(false));
    child.once("exit", (code) => resolve(code === 0));
  });
  const timed = new Promise((resolve) => {
    timer = setTimeout(async () => { await terminate(child); resolve(false); }, Math.min(milliseconds, workflowDeadline - Date.now()));
  });
  const ok = await Promise.race([finished, timed]);
  clearTimeout(timer);
  await terminate(child);
  return ok;
}

async function waitForServer(child) {
  for (let count = 0; count < 80 && Date.now() < workflowDeadline; count++) {
    if (child.exitCode !== null) throw new Error("Production server stopped.");
    try { await fetch("http://127.0.0.1:4173/", { signal: AbortSignal.timeout(1000), redirect: "manual" }); return; }
    catch { await new Promise((resolve) => setTimeout(resolve, 250)); }
  }
  throw new Error("Production server was unavailable.");
}

async function render(manifest, cwd, output) {
  const executable = path.join(cwd, "node_modules", "next", "dist", "bin", "next");
  await fs.access(executable);
  const server = spawn(process.execPath, [executable, "start", "-H", "127.0.0.1", "-p", "4173"], {
    cwd, env: { ...childEnvironment(), NODE_ENV: "production" }, stdio: "ignore", detached: true, shell: false,
  });
  let browser;
  try {
    await waitForServer(server);
    const { chromium } = await import("playwright");
    browser = await chromium.launch({ headless: true });
    const results = [];
    await fs.mkdir(path.join(output, "screenshots"), { recursive: true });
    for (const [index, target] of manifest.targets.entries()) {
      if (Date.now() >= workflowDeadline) throw new Error("Rendering deadline exceeded.");
      const context = await browser.newContext({ viewport: { width: 1365, height: 900 }, serviceWorkers: "block" });
      // Target JavaScript runs in a disposable VM; browser requests stay on its loopback server.
      await context.route("**/*", async (route) => {
        const url = new URL(route.request().url());
        return url.origin === "http://127.0.0.1:4173" ? route.continue() : route.abort();
      });
      const page = await context.newPage();
      let consoleErrors = 0, pageErrors = 0;
      page.on("console", (message) => { if (message.type() === "error") consoleErrors = Math.min(consoleErrors + 1, 1000); });
      page.on("pageerror", () => { pageErrors = Math.min(pageErrors + 1, 1000); });
      const response = await page.goto(`http://127.0.0.1:4173${target.route}`, { waitUntil: "networkidle", timeout: 20000 });
      if (page.url() !== new URL(target.route, "http://127.0.0.1:4173").href) throw new Error("An affected route redirected.");
      const metadata = await page.evaluate((productionUrl) => ({
        title: document.title.trim().slice(0, 500),
        description: (document.querySelector('meta[name="description"]')?.getAttribute("content") ?? "").trim().slice(0, 2000),
        canonical: [...document.querySelectorAll('link[rel~="canonical"]')].slice(0, 10)
          .map((node) => new URL(node.getAttribute("href") ?? "", productionUrl).href),
        robots: [...document.querySelectorAll("meta[name]")]
          .filter((node) => ["robots", "googlebot", "bingbot"].includes(node.getAttribute("name").toLowerCase()))
          .slice(0, 10).map((node) => `${node.getAttribute("name").toLowerCase()}: ${(node.getAttribute("content") ?? "").trim()}`),
        content_characters: Math.min((document.body?.innerText ?? "").trim().length, 1000000),
      }), target.url);
      const headerRobots = response?.headers()["x-robots-tag"]?.trim();
      if (headerRobots) metadata.robots.push(`X-Robots-Tag: ${headerRobots}`);
      const screenshot = `screenshots/page-${index + 1}.png`;
      const pixels = await page.screenshot({ fullPage: false, animations: "disabled" });
      if (pixels.length > MAX_SCREENSHOT) throw new Error("Screenshot exceeded the size limit.");
      await fs.writeFile(path.join(output, screenshot), pixels);
      const actual = { ...metadata, status_code: response?.status() ?? 0, console_errors: consoleErrors, page_errors: pageErrors };
      results.push({ url: target.url, route: target.route, ...actual, checks: pageChecks(actual, target), screenshot });
      await context.close();
    }
    return results;
  } finally {
    await browser?.close();
    await terminate(server);
  }
}

async function main() {
  if (process.env.GITHUB_ACTIONS !== "true" || process.platform !== "linux") throw new Error("This runner requires a GitHub-hosted Linux job.");
  const event = JSON.parse(await fs.readFile(process.env.GITHUB_EVENT_PATH, "utf8"));
  const head = event.pull_request?.head;
  if (!head || head.repo?.full_name !== process.env.GITHUB_REPOSITORY || !head.ref?.startsWith("seopilot/")
      || event.pull_request.draft !== true) throw new Error("An owned SEOPilot draft PR is required.");
  const manifest = readManifest(event.pull_request.body, head.sha);
  const output = path.resolve(process.env.SEOPILOT_OUTPUT_DIRECTORY);
  const root = await fs.realpath(process.env.SEOPILOT_TARGET_ROOT);
  const cwd = await fs.realpath(appDirectory(root, manifest.app_subdirectory));
  if (cwd !== root && !cwd.startsWith(`${root}${path.sep}`)) throw new Error("App directory resolved outside checkout.");
  await fs.mkdir(output, { recursive: true });
  const report = { schema_version: 1, fix_run_id: manifest.fix_run_id, patch_hash: manifest.patch_hash,
    head_sha: head.sha, run_id: process.env.GITHUB_RUN_ID, status: "failed", checks, targets: [] };
  try {
    const lock = await fs.stat(path.join(cwd, "package-lock.json"));
    if (lock.size > 10 * 1024 * 1024) throw new Error("Package lock is too large.");
    const packageText = await fs.readFile(path.join(cwd, "package.json"), "utf8");
    if (Buffer.byteLength(packageText) > 1024 * 1024) throw new Error("Package manifest is too large.");
    const scripts = JSON.parse(packageText).scripts ?? {};
    if (typeof scripts.build !== "string") throw new Error("A declared production build is required.");
    if (!await command(["ci"], cwd, 120000)) throw new Error("Dependency installation failed.");
    check("install", "passed");
    for (const name of ["lint", "typecheck", "test"]) {
      const script = name === "typecheck" && !scripts.typecheck && scripts["type-check"] ? "type-check" : name;
      if (typeof scripts[script] === "string") check(name, await command(["run", script], cwd, 45000) ? "passed" : "failed");
    }
    if (!await command(["run", "build"], cwd, 150000)) throw new Error("Production build failed.");
    check("build", "passed");
    report.targets = await render(manifest, cwd, output);
    check("render", "passed");
    if (checks.every((item) => item.status !== "failed") && report.targets.every((target) => target.checks.every((item) => item.status === "passed"))) report.status = "passed";
  } catch {
    // The fixed status/check names identify failure without exporting source or arbitrary script output.
  } finally {
    const json = JSON.stringify(report, null, 2);
    if (Buffer.byteLength(json) > MAX_REPORT) throw new Error("Validation report exceeded the size limit.");
    await fs.writeFile(path.join(output, "validation.json"), json);
  }
  console.log(`SEOPilot validation ${report.status}. Checks: ${checks.map((item) => `${item.name}=${item.status}`).join(", ")}`);
  if (report.status !== "passed") process.exitCode = 1;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch(() => { console.error("SEOPilot could not validate the trusted workflow inputs."); process.exitCode = 1; });
}
