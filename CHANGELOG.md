# Change log

Record each meaningful project change during the event, newest first. Update this file in the same commit as the change. Use a real timestamp with timezone, for example `YYYY-MM-DDTHH:MM:SS+05:30`.

## Event build log

## 2026-10-24T18:17:15+00:00 — Persist abuse limits and protect optional AI spending

- Changed: Added blank-key GPT-6-Luna environment template and ignored local copy, durable three-audits/IP/rolling-24h admissions, HMAC identities, duplicate reuse, schema-2 migration, per-call global AI allowance, opt-out/kill switch, strict model/input/output bounds, fixed provider endpoint, and authenticated socket-derived proxy identity. Added safe local launcher, private-file/staged/history checks, offline regressions and updated setup/security documentation.
- Why: Prevent repeated clicks, forged forwarding headers, restarts, concurrent requests and provider failures from creating unbounded paid work; keep credentials server-side and outside Git/browser bundles.
- Validation: 205 backend tests and six Node proxy tests passed; Ruff, ESLint, TypeScript, production build, ignore-rule/history checks and harmless server-secret canary check passed. Independent review found and resolved legacy unsafe launch commands and malformed-token handling. No credentials or paid API calls were used.
- Limitations: Local/single-user release; public hosting still needs authentication, ownership and trusted edge controls. Application allowance is a request ceiling, not billing telemetry. Live model access and rendered browser/mobile checks remain unverified; human review pending.

## 2026-10-24T23:14:03+05:30 — Record the verified implementation revision

- Changed: Recorded implementation SHA f66d76108a0f0fd3d11df2c2d0f9862f0be7f42d in SUBMISSION.md.
- Why: Give the demonstration and validation record a stable source revision without rewriting history or implying organizer submission.
- Validation: Resolved the SHA with Git; repository file/credential-pattern/link and diff checks passed before publication. Application source is unchanged.
- Limitations: Previously documented browser and live-AI verification limits remain; human review and organizer submission are pending.

## 2026-10-24T23:13:00+05:30 — Verify the complete workflow and document reproducible delivery

- Changed: Added API-to-storage integration tests, real bounded API smoke command, publishable-file/credential-pattern/Markdown-link checks, architecture/scoring/limitations documentation, exact Windows setup and demonstration commands, and an honest submission record. Removed trailing blank lines from crawler files.
- Why: Deliver a reproducible local product with explicit evidence for what passed and what remains unverified.
- Validation: Final backend suite177passed with one upstream TestClient deprecation warning; Ruff, frontend ESLint/TypeScript and production build passed. Regenerated API types show no drift. Dependency and repository checks passed. Atomic push dry run confirmed Git write access; actual publication is recorded after pushing.
- Limitations: Browser origin policy prevented rendered desktop/mobile/E2E and screenshot verification even after user approval/retry. Live AI awaits credentials. No Search Console, hosting or organizer submission claimed.

## 2026-10-24T22:58:22+05:30 — Add optional evidence-reviewed AI and labelled demonstration

- Changed: Added provider interface, bounded structured OpenAI Responses analysis/review, evidence ownership and quotation checks, unsupported-claim and conflict rejection, deterministic reporting/fallback, and a fixture demo using production extraction/rules with curated suggestions.
- Why: Add useful contextual recommendations without inventing audit measurements or requiring paid credentials for the core product.
- Validation: The full 177-test suite passed; offline provider tests cover missing credentials, malformed outputs, timeouts, evidence mismatches, reviewer decisions and SDK request configuration. No live AI calls or key creation occurred.
- Limitations: Live provider/model/account compatibility awaits user-supplied OPENAI_API_KEY and OPENAI_MODEL. Demo suggestions are explicitly sample data, not live model output.

## 2026-10-24T22:56:17+05:30 — Add the connected audit dashboard and human review

- Changed: Added Next.js/React/Tailwind dashboard, generated OpenAPI types, URL/context/crawl controls, real progress polling, summary/severity/coverage views, evidence filters, recommendation decisions, copy actions, pages and persistent history. Added desktop/mobile browser test scenarios and design reference.
- Why: Turn actual audit evidence into a cohesive workflow for small-business users while keeping all external website changes manual.
- Validation: Frontend production build, TypeScript and ESLint passed. Static independent review found and fixed initialization races, filtering of grouped findings, and misleading zero-assessment states.
- Limitations: Browser origin policy continues to deny localhost despite explicit user approval and a reported permission change. Browser scenarios and rendered fidelity remain unverified; no screenshot or responsive QA pass is claimed.

## 2026-10-24T22:49:40+05:30 — Safely crawl public websites and extract bounded evidence

- Changed: Added public-address validation, DNS-pinned HTTPcore transport with verified TLS and bounded address fallback, redirects, response limits/decompression, Protego crawl policy, bounded breadth-first crawling, sitemap evidence, shared extraction, truncation-aware rules, and resilient queue integration.
- Why: Make real website audits functional without allowing private-network access or treating unavailable coverage as verified findings.
- Validation: 177 backend tests passed, including 126 network/crawler/extraction cases; Ruff passed. Live example.com API audit completed: one page assessed, six findings, score82, AI unavailable. Independent transport/lifecycle review findings were fixed and covered.
- Limitations: Strict origin boundaries and server-rendered HTML only. One upstream Starlette TestClient deprecation warning. Browser verification is a later milestone.

## 2026-10-24T22:30:24+05:30 — Audit extracted evidence and explain health scoring

- Changed: Added reusable deterministic SEO rules, duplicate grouping, evidence-bearing findings, actionable rule recommendations, configurable editorial thresholds, and page-normalized scoring.
- Why: Produce explainable observations without relying on AI or inventing unavailable coverage or performance data.
- Validation: 18 focused rule tests passed; scoped Ruff passed; reviewed unknown-page exclusion, duplicate deduplication, HTTP-error handling, and context-sensitive advice.
- Limitations: This milestone operates on extracted page models; crawler/API/dashboard integration follows. No orphan or search-performance claims are produced.

## 2026-10-24T22:16:33+05:30 — Add the local API and persistence foundation

- Changed: Added typed Pydantic audit contracts, SQLite projects/audits/pages/issues/recommendations/decision records, queue recovery, loopback API guards, OpenAPI export, and backend dependency configuration. Added reproducible setup instructions and local-data ignore rules.
- Why: Establish a durable, reviewable foundation for the approved website-to-audit workflow while preserving the original remote history.
- Validation: Isolated backend dependencies installed; 5 storage/API contract tests passed; scoped Ruff checks and `git diff --check` passed. Reviewed parameterized queries, body/origin guards, queue transactions, and restart handling.
- Limitations: Crawler, rules, AI, and dashboard are subsequent milestones. Starlette emits one upstream HTTPX TestClient deprecation warning. No live AI calls made. Human review pending.

No project implementation has been recorded yet. Replace this sentence with entries as you build:

```text
## <actual timestamp> — <short change title>

- Changed: <feature or files changed>
- Why: <reason for the change>
- Validation: <commands or manual checks actually run, with results>
- Limitations: <known issues or "None identified in these checks">
```

## Template setup — 10 October 2026

- Changed: Added the event README, rules, agent guide, change log, AI usage record, submission checklist, Git ignore rules, and pull request checklist.
- Why: Give participants a consistent starting point for event rules, basic coding patterns, documented changes, and regular commits.
- Validation: Checked local Markdown links, event detail consistency, required documents, and diff whitespace before publishing.
- Limitations: Documentation scaffolding only; no participant project, application, or working demo is included. GitHub publication and template status are verified separately after creation.
