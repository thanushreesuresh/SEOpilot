import { readFile } from "node:fs/promises";
import { isIP } from "node:net";
import path from "node:path";
import type { NextApiRequest, NextApiResponse } from "next";

const MAX_BODY_BYTES = 16 * 1024;
const UPSTREAM = "http://127.0.0.1:8000/api/";
const UUID = "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}";
const AUDIT_PATH = new RegExp(`^audits/${UUID}$`, "i");
const AUDIT_CANCEL = new RegExp(`^audits/${UUID}/cancel$`, "i");
const DECISION_PATH = new RegExp(`^recommendations/${UUID}/decision$`, "i");
const FIX_PATH = new RegExp(`^fix-runs/${UUID}$`, "i");
const FIX_READ = new RegExp(`^fix-runs/${UUID}/patch$`, "i");
const FIX_ACTION = new RegExp(`^fix-runs/${UUID}/(publish|cancel|delete-source|verify|refresh)$`, "i");
const DISPOSITION = new RegExp(`^audits/${UUID}/issues/${UUID}/disposition$`, "i");
const DISPOSITIONS = new RegExp(`^audits/${UUID}/dispositions$`, "i");
const DISCONNECT = new RegExp(`^projects/${UUID}/disconnect$`, "i");
const AUDIT_REPORT = new RegExp(`^audits/${UUID}/report/(markdown|csv|json)$`, "i");
const RESPONSE_HEADERS = ["retry-after", "ratelimit-limit", "ratelimit-remaining", "ratelimit-reset", "x-audit-reused"];

type Dependencies = {
  fetchUpstream: typeof fetch;
  readToken: () => Promise<string>;
};

async function readToken() {
  const filename = process.env.SEOPILOT_PROXY_TOKEN_FILE || path.resolve(process.cwd(), "../backend/.data/proxy-token");
  // This private runtime file must never be traced into a production bundle.
  const token = (await readFile(/*turbopackIgnore: true*/ filename, "utf8")).trim();
  if (!/^[0-9a-f]{64}$/.test(token)) throw new Error("Invalid proxy configuration");
  return token;
}

function allowedMethod(route: string) {
  if (["health", "usage"].includes(route) || AUDIT_PATH.test(route)) return "GET";
  if (route === "audits") return "GET, POST";
  if (route === "demo-audits") return "POST";
  if (AUDIT_CANCEL.test(route)) return "POST";
  if (DECISION_PATH.test(route)) return "PATCH";
  if (["github/connection"].includes(route) || FIX_PATH.test(route) || FIX_READ.test(route) || DISPOSITIONS.test(route)) return "GET";
  if (["projects", "fix-runs"].includes(route)) return "GET, POST";
  if (FIX_ACTION.test(route) || DISCONNECT.test(route)) return "POST";
  if (DISPOSITION.test(route)) return "PATCH";
  if (route === "audit-comparisons") return "POST";
  if (AUDIT_REPORT.test(route)) return "GET";
  return "";
}

function jsonError(response: NextApiResponse, status: number, detail: string) {
  response.status(status).json({ detail });
}

// Only this server-side module sees the private proxy token or chooses the upstream.
export async function proxyRequest(request: NextApiRequest, response: NextApiResponse, dependencies: Dependencies = { fetchUpstream: fetch, readToken }) {
  response.setHeader("Cache-Control", "no-store");
  response.setHeader("X-Content-Type-Options", "nosniff");
  const segments = request.query.path;
  const route = Array.isArray(segments) ? segments.join("/") : "";
  const methods = allowedMethod(route);
  if (!methods || request.url?.includes("?")) return jsonError(response, 404, "Unknown API route.");
  if (!request.method || !methods.split(", ").includes(request.method)) {
    response.setHeader("Allow", methods);
    return jsonError(response, 405, "Method not allowed.");
  }
  const address = request.socket.remoteAddress;
  if (!address || !isIP(address)) return jsonError(response, 503, "The audit service is unavailable.");

  const chunks: Buffer[] = [];
  let bodyBytes = 0;
  try {
    for await (const chunk of request) {
      const buffer = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
      bodyBytes += buffer.byteLength;
      if (bodyBytes > MAX_BODY_BYTES) return jsonError(response, 413, "Request body is too large.");
      chunks.push(buffer);
    }
  } catch { return jsonError(response, 400, "Could not read the request."); }

  const abort = new AbortController();
  const deadline = setTimeout(() => abort.abort(), 10_000);
  try {
    const token = await dependencies.readToken();
    if (!/^[0-9a-f]{64}$/.test(token)) throw new Error("Invalid proxy configuration");
    const headers = new Headers({ "x-seopilot-proxy-token": token, "x-seopilot-client-ip": address });
    for (const name of ["content-type", "origin", "sec-fetch-site"]) {
      const value = request.headers[name];
      if (typeof value === "string") headers.set(name, value);
    }
    const upstream = await dependencies.fetchUpstream(`${UPSTREAM}${route}`, {
      method: request.method,
      headers,
      body: ["POST", "PATCH"].includes(request.method) ? Buffer.concat(chunks) : undefined,
      redirect: "error",
      signal: abort.signal,
      cache: "no-store",
    });
    for (const name of RESPONSE_HEADERS) {
      const value = upstream.headers.get(name);
      if (value) response.setHeader(name, value);
    }
    response.setHeader("Content-Type", "application/json; charset=utf-8");
    response.status(upstream.status).send(Buffer.from(await upstream.arrayBuffer()));
  } catch { jsonError(response, 503, "The audit service is unavailable. Check that the backend is running."); }
  finally { clearTimeout(deadline); }
}
