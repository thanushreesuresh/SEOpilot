import assert from "node:assert/strict";
import { Readable } from "node:stream";
import test from "node:test";
import { proxyRequest } from "../src/lib/server-proxy.ts";

const TOKEN = "a".repeat(64);

test("v2 proxy forwards only explicit UUID routes and methods", async () => {
  const id = "12345678-1234-1234-1234-123456789abc";
  const allowed = [["github/connection", "GET"], ["projects", "POST"], [`projects/${id}/disconnect`, "POST"],
    ["audit-comparisons", "POST"], [`audits/${id}/cancel`, "POST"], ...["markdown", "csv", "json"].map((format) => [`audits/${id}/report/${format}`, "GET"]),
    ["fix-runs", "POST"], [`fix-runs/${id}`, "GET"], [`fix-runs/${id}/patch`, "GET"],
    ...["publish", "cancel", "delete-source", "verify"].map((action) => [`fix-runs/${id}/${action}`, "POST"]),
    [`audits/${id}/issues/${id}/disposition`, "PATCH"], [`audits/${id}/dispositions`, "GET"]];
  for (const [route, method] of allowed) {
    const res = response();
    let called = false;
    await proxyRequest(request(route, method, method === "GET" ? [] : ["{}"]), res, {
      readToken: async () => TOKEN, fetchUpstream: async (url) => { called = true; assert.equal(url, `http://127.0.0.1:8000/api/${route}`); return new Response("{}"); },
    });
    assert.equal(called, true, route);
  }
  for (const route of [`fix-runs/${id}/merge`, `projects/${id}/secrets`, `audits/${id}/report/html`, "audits/forged/report/json", "audits/forged/cancel", "github/token", "fix-runs/forged/publish", "fix-runs?project_id=x"]) {
    const res = response();
    await proxyRequest(request(route, "POST"), res, { readToken: async () => { throw new Error("must not reach upstream"); }, fetchUpstream: fetch });
    assert.equal(res.statusCode, 404, route);
  }
});

function request(route = "audits", method = "GET", chunks = [], headers = {}) {
  const stream = Readable.from(chunks);
  stream.query = { path: route.split("/") };
  stream.url = `/api/${route}`;
  stream.method = method;
  stream.headers = headers;
  stream.socket = { remoteAddress: "::ffff:203.0.113.42" };
  return stream;
}

function response() {
  return {
    statusCode: 200,
    headers: {},
    body: null,
    setHeader(name, value) { this.headers[name.toLowerCase()] = value; return this; },
    status(value) { this.statusCode = value; return this; },
    json(body) { this.body = body; return this; },
    send(body) { this.body = body; return this; },
  };
}

test("proxy authenticates the socket IP and never forwards spoofed identity or secrets", async () => {
  const req = request("audits", "POST", ["{}"], {
    "content-type": "application/json",
    "origin": "http://localhost:3000",
    "sec-fetch-site": "same-origin",
    "x-seopilot-proxy-token": "attacker",
    "x-seopilot-client-ip": "8.8.8.8",
    "x-forwarded-for": "8.8.8.8",
    "forwarded": "for=8.8.8.8",
    "authorization": "Bearer attacker",
    "cookie": "private=value",
    "host": "attacker.example",
  });
  const res = response();
  await proxyRequest(req, res, {
    readToken: async () => TOKEN,
    fetchUpstream: async (url, init) => {
      assert.equal(url, "http://127.0.0.1:8000/api/audits");
      assert.equal(init.headers.get("x-seopilot-proxy-token"), TOKEN);
      assert.equal(init.headers.get("x-seopilot-client-ip"), req.socket.remoteAddress);
      assert.equal(init.headers.get("origin"), "http://localhost:3000");
      assert.equal(init.body.toString(), "{}");
      assert.equal(init.redirect, "error");
      for (const name of ["x-forwarded-for", "forwarded", "authorization", "cookie", "host"]) assert.equal(init.headers.has(name), false);
      return new Response('{"id":"test"}', { status: 202, headers: { "x-audit-reused": "true", "set-cookie": "secret=value", "x-seopilot-proxy-token": TOKEN } });
    },
  });
  assert.equal(res.statusCode, 202);
  assert.equal(res.headers["x-audit-reused"], "true");
  assert.equal(res.headers["cache-control"], "no-store");
  assert.equal(res.headers["set-cookie"], undefined);
  assert.equal(res.headers["x-seopilot-proxy-token"], undefined);
  assert.equal(res.body.toString(), '{"id":"test"}');
});

test("proxy copies retry and quota headers on a rejected request", async () => {
  const res = response();
  await proxyRequest(request(), res, {
    readToken: async () => TOKEN,
    fetchUpstream: async () => new Response('{"detail":"Daily allowance reached"}', { status: 429, headers: { "retry-after": "120", "ratelimit-limit": "3", "ratelimit-remaining": "0", "ratelimit-reset": "120" } }),
  });
  assert.equal(res.statusCode, 429);
  assert.equal(res.headers["retry-after"], "120");
  assert.equal(res.headers["ratelimit-remaining"], "0");
});

test("unknown routes, query strings and wrong methods never reach the backend", async () => {
  const fetchUpstream = async () => { assert.fail("Unexpected upstream request"); };
  for (const [route, method, status] of [["https://attacker.example", "GET", 404], ["../health", "GET", 404], ["audits/not-a-uuid", "GET", 404], ["health", "POST", 405], ["demo-audits", "GET", 405]]) {
    const res = response();
    await proxyRequest(request(route, method), res, { readToken: async () => TOKEN, fetchUpstream });
    assert.equal(res.statusCode, status);
  }
  const req = request(); req.url += "?upstream=https://attacker.example";
  const res = response();
  await proxyRequest(req, res, { readToken: async () => TOKEN, fetchUpstream });
  assert.equal(res.statusCode, 404);
});

test("oversized streamed bodies are rejected before token access or networking", async () => {
  const res = response();
  await proxyRequest(request("audits", "POST", ["a".repeat(10_000), "b".repeat(10_000)]), res, {
    readToken: async () => { assert.fail("Unexpected token read"); },
    fetchUpstream: async () => { assert.fail("Unexpected upstream request"); },
  });
  assert.equal(res.statusCode, 413);
});

test("an unavailable token, invalid socket IP or failed backend produces a sanitized 503", async () => {
  for (const dependencies of [
    { readToken: async () => { throw new Error("private file path and secret"); }, fetchUpstream: async () => { assert.fail(); } },
    { readToken: async () => "bad-token", fetchUpstream: async () => { assert.fail(); } },
    { readToken: async () => TOKEN, fetchUpstream: async () => { throw new Error(`private secret ${TOKEN}`); } },
  ]) {
    const res = response(); await proxyRequest(request(), res, dependencies);
    assert.equal(res.statusCode, 503);
    assert.doesNotMatch(JSON.stringify(res.body), /private|secret|aaaa/);
  }
  const req = request(); req.socket.remoteAddress = undefined;
  const res = response();
  await proxyRequest(req, res, { readToken: async () => { assert.fail(); }, fetchUpstream: async () => { assert.fail(); } });
  assert.equal(res.statusCode, 503);
});

test("only the exact detail and recommendation UUID routes are admitted", async () => {
  const id = "ec92de63-ff25-4868-a688-9b7268b56eb2";
  for (const [route, method] of [[`audits/${id}`, "GET"], [`recommendations/${id}/decision`, "PATCH"], ["usage", "GET"], ["health", "GET"], ["demo-audits", "POST"]]) {
    const res = response();
    await proxyRequest(request(route, method), res, { readToken: async () => TOKEN, fetchUpstream: async () => new Response("{}") });
    assert.equal(res.statusCode, 200);
  }
});
