import assert from "node:assert/strict";
import test from "node:test";
import { appDirectory, pageChecks, readManifest, safeRoute } from "../lib.mjs";

const SHA = "a".repeat(40);
function manifest() {
  return { schema_version: 1, fix_run_id: "11111111-1111-4111-8111-111111111111", patch_hash: "b".repeat(64),
    app_subdirectory: "frontend", targets: [{ url: "https://example.com/about", route: "/about", title: "About Café \"Works\"",
      description: "Explore useful services, real information and a thoughtful team.",
      canonical: ["https://example.com/about"], robots: ["robots: index, follow"] }] };
}
const body = (value) => `A reviewed draft.\n<!-- seopilot-manifest\n${JSON.stringify(value)}\n-->`;

test("reads one bounded Unicode manifest without treating text as shell", () => {
  const value = manifest();
  value.targets[0].description = "$(touch /tmp/nope) `node -e nope` <script>text</script>";
  assert.deepEqual(readManifest(body(value), SHA), value);
});

test("rejects wrong head, repeated markers and too many targets", () => {
  const value = manifest();
  value.head_sha = "c".repeat(40);
  assert.throws(() => readManifest(body(value), SHA));
  assert.throws(() => readManifest(`${body(manifest())}\n${body(manifest())}`, SHA));
  value.targets = Array(4).fill(value.targets[0]);
  assert.throws(() => readManifest(body(value), SHA));
});

test("requires a single production origin, no credentials and unique pages", () => {
  for (const url of ["https://user:secret@example.com/about", "file:///etc/passwd", "https://example.com/about?x=1"]) {
    const value = manifest(); value.targets[0].url = url;
    assert.throws(() => readManifest(body(value), SHA));
  }
  const value = manifest();
  value.targets.push({ ...value.targets[0] });
  assert.throws(() => readManifest(body(value), SHA));
  value.targets[1].url = "https://different.example/about";
  assert.throws(() => readManifest(body(value), SHA));
});

test("rejects traversal, redirects and query based route escapes", () => {
  for (const route of ["//evil.example/", "/../secret", "/%2e%2e/secret", "/\\evil", "/x?next=evil", "/x#fragment", "/%00", "/%5cevil"]) {
    assert.equal(safeRoute(route), false, route);
  }
  assert.equal(safeRoute("/about"), true);
  assert.equal(safeRoute("/café"), true);
});

test("rejects unsafe app directories", () => {
  for (const app_subdirectory of ["../other", "/absolute", "a/../b", "a\\b", ".git", "frontend;curl"]) {
    const value = manifest(); value.app_subdirectory = app_subdirectory;
    assert.throws(() => readManifest(body(value), SHA));
  }
  assert.throws(() => appDirectory("/repo", "../elsewhere"));
  assert.equal(appDirectory("/repo", "frontend"), appDirectory("/repo/frontend", ""));
});

test("metadata comparisons preserve canonical and indexing directives", () => {
  const target = manifest().targets[0];
  const actual = { ...target, status_code: 200, content_characters: 120, console_errors: 0, page_errors: 0 };
  assert.ok(pageChecks(actual, target).every((item) => item.status === "passed"));
  actual.description = "Different";
  actual.robots = ["robots: noindex"];
  actual.canonical = [];
  actual.console_errors = 1;
  const failed = pageChecks(actual, target).filter((item) => item.status === "failed").map((item) => item.name);
  assert.deepEqual(failed, ["description", "console", "canonical", "robots"]);
});

test("HTTP failure and blank pages cannot pass rendering", () => {
  const target = manifest().targets[0];
  const actual = { ...target, status_code: 500, content_characters: 0, console_errors: 0, page_errors: 1 };
  const failed = pageChecks(actual, target).filter((item) => item.status === "failed").map((item) => item.name);
  assert.deepEqual(failed, ["http", "content", "page_errors"]);
});
