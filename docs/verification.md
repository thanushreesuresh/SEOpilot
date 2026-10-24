# Verification and delivery record

Checked on 24 October 2026, using Node 22.17.0, Python 3.13.6, Next.js 16.4.3 and the committed dependency lockfiles.

| Check | Result |
| --- | --- |
| Complete backend pytest suite | 205 passed |
| Node authenticated-proxy tests | 6 passed |
| GitHub Actions offline workflow | [Passed](https://github.com/thanushreesuresh/SEOpilot/actions/runs/40120505329) on Linux for implementation commit `3a90c3c` |
| Ruff, backend and scripts | Passed |
| Frontend ESLint | Passed without warnings |
| TypeScript | Passed |
| Next.js production build | Passed |
| Regenerated OpenAPI/frontend type drift | No changes |
| Working/staged files, reachable Git history, credential patterns, ignore rules and Markdown links | Passed; no credential values printed |
| Server-secret marker in client assets | Absent after production build with harmless canary |
| Dependency consistency | pip check passed; npm install reported 0 vulnerabilities |
| Real pinned HTTPS fetch | example.com returned HTTP 200 |
| Real local audit API | Completed: one page assessed, six findings, score 82, AI unavailable |
| Offline AI/provider contracts | Passed within backend suite; no paid requests |
| Browser desktop/mobile scenarios | Not run: local-origin permission policy denied access |
| Browser screenshot/concept fidelity | Not verified; no implementation screenshot captured |

Backend tests cover restricted IPs and URL forms, mixed DNS answers, pinned TCP/Host/SNI and normal TLS verification, fallback between validated addresses, redirects, time/size/decompression limits, binary responses, robots matching/policy errors, sitemap evidence, crawl budgets, extraction bounds, deterministic rules, duplicate detection, scoring, AI schemas/grounding/review, queue recovery, API guards, approvals/rejections and history.

Security additions were checked offline: parallel admissions from separate Store instances cannot exceed three per identity; quotas and global paid-call reservations survive reopening the database; exact rolling-window expiry, full-queue/invalid-input nonconsumption, duplicate reuse, IPv4-mapped and IPv6 subnet grouping, forged/duplicate/malformed private headers, opt-out/kill switch, fixed provider endpoint, disabled environment proxies, input/output caps and withheld unreviewed output are covered. Node tests check fixed proxy host, socket identity, header stripping, route/method allowlists, body bounds, sanitized failures and forwarded quota/retry headers. Independent review found and resolved unsafe legacy launch instructions and non-ASCII proxy-token handling.

The API integration test replaces only the network-facing crawl seam with bundled fixture extraction. The real runner, rules, score, API, SQLite storage and decisions execute. A separate live API smoke test fetched actual example.com HTML. Its recorded values are observations from that run, not expected results for future audits.

Independent review found and fixed validated-address fallback, worker claim recovery, a frontend initialization race, duplicate-group URL filtering and misleading zero-assessment messaging. The last three frontend fixes passed static checks and build; browser behavior remains unverified.

## Limitations and resolved environment failures

- Starlette emits one upstream deprecation warning for its HTTPX TestClient integration. Tests pass; the warning is not suppressed.
- The first successful hosted run also reports upstream action-runtime deprecation and runner-image migration notices; these did not fail the checks. No paid credentials are supplied to the workflow.
- Sandbox restrictions initially blocked virtual-environment bootstrap, npm registry access, temporary/event-loop resources and Turbopack's CSS child process. Scoped retries outside the sandbox completed installation, tests and build successfully.
- The in-app browser origin gate first reported declined permission, then a saved or managed deny for `http://localhost:3000`. It remained denied after explicit user approval and a reported permission change. No alternate browser or Playwright execution was attempted to bypass it. Browser test code is present for an environment with authorized access.
- Six browser scenarios are present, including allowance exhaustion and AI opt-out/duplicate reuse. They remain unexecuted under that same policy. UI additions passed static checks and the production build.
- No OpenAI credentials were created or written. A blank ignored local environment file was prepared; the harmless build canary was process-local. Live AI/model/account access has not been verified. Optional AI failures preserve deterministic results.
- Google Search Console and public hosting are not implemented. No performance measurements, deployment or organizer submission is claimed.

See README for exact setup, test commands and the demonstration. Human review remains pending in AI_USAGE.
