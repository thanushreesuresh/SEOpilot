import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import fs from "node:fs/promises";
import net from "node:net";
import path from "node:path";
import test from "node:test";
import { promisify } from "node:util";
import { requireStoppedDashboard } from "../scripts/build.mjs";

const exec = promisify(execFile);

test("a live dashboard blocks the build before existing assets are changed", async () => {
  const server = net.createServer();
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const port = server.address().port;
  const buildId = path.resolve(".next/BUILD_ID");
  const before = await fs.readFile(buildId).catch(() => null);
  try {
    await assert.rejects(exec(process.execPath, ["scripts/build.mjs"], { env: { ...process.env, PORT: String(port) } }),
      (error) => error.code === 1 && /Stop the dashboard/.test(error.stderr));
    assert.deepEqual(await fs.readFile(buildId).catch(() => null), before);
  } finally {
    await new Promise((resolve) => server.close(resolve));
  }
});

test("a closed listening port permits a build and invalid ports fail closed", async () => {
  const server = net.createServer();
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const port = server.address().port;
  await new Promise((resolve) => server.close(resolve));
  await requireStoppedDashboard(port);
  await assert.rejects(requireStoppedDashboard(NaN), /valid TCP port/);
});
