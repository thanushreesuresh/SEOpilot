import path from "node:path";

const MARKER = /<!-- seopilot-manifest\r?\n([\s\S]*?)\r?\n-->/g;
const hex = (value, length) => typeof value === "string" && new RegExp(`^[0-9a-f]{${length}}$`).test(value);
const text = (value, limit) => typeof value === "string" && value.length <= limit && !/[\u0000-\u001f]/u.test(value);
const texts = (value) => Array.isArray(value) && value.length <= 10 && value.every((entry) => text(entry, 2048));

export function safeRoute(route) {
  if (!text(route, 2048) || !route.startsWith("/") || route.startsWith("//") || /[\\?#]/u.test(route)) return false;
  try {
    const decoded = decodeURIComponent(route);
    return !/[\\?#\u0000-\u0020]/u.test(decoded) && !decoded.startsWith("//")
      && !decoded.split("/").some((part) => part === "." || part === "..")
      && new URL(route, "http://127.0.0.1:4173").origin === "http://127.0.0.1:4173";
  } catch { return false; }
}

export function readManifest(body, headSha) {
  if (typeof body !== "string" || Buffer.byteLength(body, "utf8") > 64000 || !hex(headSha, 40)) throw new Error("Invalid PR metadata.");
  const matches = [...body.matchAll(MARKER)];
  if (matches.length !== 1 || Buffer.byteLength(matches[0][1], "utf8") > 32000) throw new Error("A single bounded SEOPilot manifest is required.");
  const data = JSON.parse(matches[0][1]);
  const allowed = new Set(["schema_version", "fix_run_id", "patch_hash", "head_sha", "app_subdirectory", "targets"]);
  if (!data || typeof data !== "object" || Array.isArray(data) || Object.keys(data).some((key) => !allowed.has(key))
      || data.schema_version !== 1 || !/^[0-9a-f-]{36}$/.test(data.fix_run_id ?? "") || !hex(data.patch_hash, 64)
      || (data.head_sha !== undefined && data.head_sha !== headSha)
      || !Array.isArray(data.targets) || data.targets.length < 1 || data.targets.length > 3) throw new Error("Invalid proposal manifest.");
  data.app_subdirectory ??= "";
  if (!text(data.app_subdirectory, 200) || (data.app_subdirectory !== "" && !/^[A-Za-z0-9_.-]+(?:\/[A-Za-z0-9_.-]+)*$/.test(data.app_subdirectory))
      || data.app_subdirectory.split("/").some((part) => part === "." || part === ".." || part.startsWith("."))) throw new Error("Invalid app directory.");
  const seen = new Set();
  let origin;
  for (const target of data.targets) {
    const targetKeys = ["url", "route", "title", "description", "canonical", "robots"];
    if (!target || typeof target !== "object" || Object.keys(target).length !== targetKeys.length
        || Object.keys(target).some((key) => !targetKeys.includes(key)) || !safeRoute(target.route)
        || !text(target.url, 2048) || !text(target.title, 500) || !text(target.description, 2000)
        || !texts(target.canonical) || !texts(target.robots)) throw new Error("Invalid proposed page.");
    const url = new URL(target.url);
    if (!["http:", "https:"].includes(url.protocol) || url.username || url.password || url.hash || url.search
        || (url.port && !["80", "443"].includes(url.port)) || seen.has(target.url)
        || (origin && origin !== url.origin)) throw new Error("Invalid production URL.");
    seen.add(target.url);
    origin = url.origin;
  }
  return data;
}

export function appDirectory(root, subdirectory) {
  const directory = path.resolve(root, subdirectory);
  if (directory !== path.resolve(root) && !directory.startsWith(`${path.resolve(root)}${path.sep}`)) throw new Error("App directory escaped checkout.");
  return directory;
}

export function pageChecks(actual, target) {
  const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
  return Object.entries({
    http: actual.status_code >= 200 && actual.status_code < 300,
    title: actual.title === target.title,
    description: actual.description === target.description,
    content: actual.content_characters >= 40,
    console: actual.console_errors === 0,
    page_errors: actual.page_errors === 0,
    canonical: same(actual.canonical, target.canonical),
    robots: same(actual.robots, target.robots),
  }).map(([name, passed]) => ({ name, status: passed ? "passed" : "failed" }));
}
