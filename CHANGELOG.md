# Change log

## 2026-10-25T04:12:30+05:30 — Record verified score explanations

- Changed: Updated README, verification and submission records for source 11f46b4 and passing hosted run 40139477667. Inspected final desktop/mobile screenshots and confirmed preserved original database counts using read-only access.
- Validation: Hosted 534 backend tests, 34 AST tests, seven validator/proxy tests each, 33 browser scenarios, lint/type/build and contract/credential/history checks passed. New and legacy score explanations passed computed font-size/contrast checks. Human review remains pending.
- Limitations: Documentation-only checkpoint. No paid calls, extra probes, counter resets or website writes. Local manual restart and owned-pilot App/PR/deployment/live-verification acceptance remain pending; scores are diagnostic heuristics.

## 2026-10-25T04:05:09+05:30 — Improve score-detail readability after hosted inspection

- Changed: Increased new score explanations to 12-pixel text, used darker text colors and added hosted assertions for computed font size and text/background contrast, including legacy scores without a breakdown.
- Why: The passing 534-backend/33-browser run on 47e2d1e produced screenshots showing inherited 10-pixel muted text. Existing colors measured 3.66–3.79:1 against white; the new paragraph color measures 7.38:1. This correction is limited to the new score details.
- Validation: Prior hosted run 40138903220 passed all functional checks. Independent specification review identified the unwrapped legacy paragraph; it now shares the scoped styling and readability assertions. Corrected frontend lint/types/build and credential/link checks passed; both final independent review axes found no remaining actionable issues. Hosted verification pending. No scorer, provider, quota or persistence behavior changes; human review pending.

## 2026-10-25T03:58:30+05:30 — Reuse saved browser fixtures under the real burst limit

- Changed: Shared browser sample setup now reads history/detail and creates a sample only when none exists; API failures include their HTTP status in assertions. Updated audit, cancellation, discovery and score scenarios to use it.
- Why: Hosted traces proved all four new score scenarios received HTTP 429 before reaching UI assertions because the suite made redundant sample-creation requests inside one minute. The production burst guard correctly remained active; its limits and behavior are unchanged.
- Validation: Source 270a6e5 passed 534 backend tests, all static/build/contract checks and 29 existing hosted browser scenarios; the four new browser scenarios failed at setup. Frontend lint/type checks and credential/link checks passed for this correction; independent standards/specification reviews found no actionable issues. Hosted rerun and human review pending; no paid calls or user-counter changes.

## 2026-10-25T03:51:30+05:30 — Explain recorded health-score deductions

- Changed: Added an optional persisted score breakdown from the existing scoring aggregation, page/site deductions and exclusions in the dashboard, URL search links to findings, generated contracts and Markdown/CSV/JSON report support. Older scores stay explicitly unrecorded and unchanged.
- Why: A score and formula alone did not show which observed page/rule deductions contributed, whether caps or HTTP-error overrides applied, or why missing coverage could not improve the denominator.
- Validation: Baseline 521 and final 534 backend tests passed locally; Ruff, frontend ESLint/TypeScript, 34 AST tests, seven validator/proxy tests each and production build passed. Independent standards/specification reviews found no actionable issues. New tests cover rule/group deduplication, caps, HTTP overrides, exclusions, rounding, persistence, review immutability and export escaping. Four desktop/mobile/legacy/no-score browser scenarios await hosted execution.
- Limitations: Diagnostic weights/formula and rule/score versions remain unchanged; deductions do not forecast gains. Counts explain retained snapshots, not undiscovered URLs. No paid AI calls, extra crawl requests, original database/counter changes or website writes. Human review, local manual restart and owned-pilot acceptance remain pending.

## 2026-10-25T03:40:59+05:30 — Record verified discovery evidence

- Changed: Updated README, verification and submission records with source 78dd569 and passing hosted run 40137186217; inspected hosted desktop/mobile screenshots and confirmed original database counts with read-only access.
- Validation: Hosted 521 backend tests, 34 AST tests, seven validator/proxy tests each, 29 Chromium scenarios, lint/type/build and contract/credential/history checks passed. Local full checks passed; human review remains pending.
- Limitations: Documentation-only checkpoint. No new probes, paid calls, counter resets or website writes. Local manual restart and owned-pilot App/PR/deployment/live-verification acceptance remain pending.

## 2026-10-25T03:35:23+05:30 — Retain crawl discovery evidence

- Changed: Added bounded robots/sitemap check snapshots to audit contracts, crawler progress, persistence, demo, dashboard and Markdown/CSV/JSON exports. Successful checks can substantiate missing-policy resolution in comparisons only with matching rules, finished analysis and the same nonempty assessed scope.
- Why: Earlier audits discarded successful probes, leaving users without an explanation of inspected discovery locations and preventing evidence-backed comparison of previously missing files. Older snapshots remain explicitly unknown; history and scoring versions are preserved.
- Validation: Baseline 498 and final 521 backend tests passed locally; Ruff, frontend ESLint/TypeScript, 34 AST tests, seven validator/proxy tests each and production build passed. Independent standards and specification reviews found no actionable issues. Added three desktop/mobile/legacy browser scenarios for hosted execution; hosted results pending at this checkpoint.
- Limitations: A recognized XML root does not verify listed URLs, orphan detection, indexing or ranking outcomes. Interrupted request counts describe the last persisted update. No additional probes or AI calls, original database/counter changes, or website writes; human review and owned-pilot acceptance remain pending. Local service restart remains a manual step following the earlier automatic approval rejection.

## 2026-10-25T03:22:10+05:30 — Record verified cancellation and shutdown recovery

- Changed: Updated delivery records for source da67735 and successful hosted run 40135903810; documented the original database counts and remaining local/pilot setup steps.
- Validation: Hosted 498 backend tests, 34 AST tests, seven validator/proxy tests each, 26 Chromium scenarios, lint/type/build and contract/credential checks all passed. Final mobile screenshot inspected. Local full suite also passed; read-only counts confirmed existing admissions and AI reservations were unchanged.
- Limitations: No new live AI requests or website writes. Local services need manual restart after the prior automatic approval rejection; owned-pilot App setup, exact-patch approval, manual merge/deploy, live verification and human review remain pending. Documentation-only checkpoint; the verified implementation SHA remains da67735.

## 2026-10-25T03:18:12+05:30 — Preserve shutdown when child cleanup fails

- Changed: Drain unobserved audit tasks even if already failed; preserve parent cancellation when child cleanup raises and log a generic warning without private exception bodies.
- Why: Two reproduced cases replaced server cancellation with a cleanup exception, leaving the worker running and incorrectly marking active work failed. A third regression covers shutdown during user-cancellation cleanup.
- Validation: All 498 backend tests passed locally in 70.58 seconds; Ruff and both independent review axes passed. Source f9368c9 passed 495 backend tests and all 26 hosted browser scenarios, and its mobile screenshot was inspected. The final backend follow-up awaits a complete hosted rerun.
- Limitations: Existing local processes still need manual restart after the earlier automatic approval rejection. No live providers, user-counter resets or website writes; human review and owned-pilot acceptance remain pending.

## 2026-10-25T03:10:42+05:30 — Match cancellation tests to accessible markup

- Changed: New browser cases select the progress panel's explicit `status` role and locate retained page evidence within its table cell.
- Why: The component intentionally overrides the section's default region role; the previous locator would not find it. Page cells also contain diagnostic summary text.
- Validation: Static comparison against the rendered component markup; frontend lint/type checks run for the correction. Hosted execution is pending; no product behavior or provider calls changed. Human review pending.

## 2026-10-25T03:06:28+05:30 — Cancel audits without resetting spending limits

- Changed: Added durable queued/running audit cancellation, an allowlisted API action and accessible dashboard control. Retained evidence supports history, exports, comparisons and recommendation review; stale writes and new AI reservations cannot resurrect a cancelled run.
- Reliability: The worker cancels/drains its active child and continues to the next audit while preserving shutdown behavior. Cancelled live verification fails and retries consume fresh admissions. Deployment comparison now reuses saved-audit evidence checks, preventing failed/interrupted/cancelled or body-truncated snapshots from verifying matching metadata or claiming unsupported finding/score improvements.
- Validation: Reproduced the missing cancellation path and 13 live-verification evidence failures before fixes. All 495 backend tests passed in 51.58 seconds, plus Ruff, seven proxy tests, ESLint, TypeScript and production build. Separate standards/spec reviews found no actionable issues. Three new browser scenarios await hosted execution; the suite now has 26.
- Limitations: Cancellation preserves accepted admissions and all paid-call reservations; requests already in progress may still be billed and cleanup is cooperative. No live credentials, production counters or website writes were used. Existing local processes need manual restart; the earlier dashboard restart was blocked by automatic approval review. Pilot App/manual deployment and human review remain pending.

## 2026-10-25T02:38:32+05:30 — Record verified saved-evidence improvements

- Changed: Updated README, architecture, verification and submission records for source 39b31e5 and hosted run 40132659834; documented stopping the dashboard before rebuilding.
- Validation: Hosted465 backend tests,34 AST tests,7 validator/proxy tests each,23 Chromium scenarios, lint/type/build, contract drift and credential/history checks all passed. Hosted mobile screenshot inspected. Saved-report API smoke preserved all existing records/counters and made zero AI calls.
- Corrections: Independent reviews corrected unfinished-analysis absence, clipped JSON-LD presence and the mobile hidden-header overflow. Intermediate failures and unsuccessful containment remain in commit history.
- Limitations: Automatic approval review blocked the final local dashboard restart with only “blocked by policy”; a read-only check found a stale stylesheet404, so manual restart is required. Pilot App setup, exact patch approval, manual merge/deploy, live verification and human review remain pending. This checkpoint changes documentation only.

## 2026-10-25T02:34:08+05:30 — Anchor the hidden history column label

- Changed: Positioned history header cells so their absolutely positioned accessible labels stay inside the table's scroll boundary. Removed the unsuccessful comparison paint-containment workaround. Browser evidence now includes a reversible static-header measurement.
- Why: An independent review identified the offscreen “Open” column label as an uncontained absolute descendant; comparison-table descendants in the earlier diagnostic were clipped correctly.
- Validation: Local ESLint, TypeScript and production build passed. The unchanged mobile width assertion and keyboard table-scroll check remain required in the hosted rerun.
- Limitations: The causal width measurement and final mobile acceptance are pending hosted execution. Local dashboard restart remains blocked by automatic approval review. No AI calls or user-counter changes; human review pending.

## 2026-10-25T02:32:41+05:30 — Isolate remaining hosted scroll overflow

- Changed: Expanded the bounded mobile diagnostic with computed scroll-region styles and reversible region-isolation measurements. The page is restored before the unchanged width assertion.
- Why: Paint containment alone did not resolve the 629-pixel document width in hosted Chromium; the same single browser case remains failed.
- Validation: ESLint and TypeScript passed. Backend465 and browser22 passed again on source 9b0d2e1; the isolated diagnostic awaits hosted execution.
- Limitations: The local dashboard needs a restart after rebuilding; automatic approval review rejected that process restart with only “blocked by policy.” No bypass attempted. API/saved data remain intact; human review pending.

## 2026-10-25T02:26:34+05:30 — Contain mobile comparison table scrolling

- Changed: Added a containing block and paint containment to the comparison table scroller; the browser scenario also verifies horizontal scrolling by keyboard.
- Why: Hosted geometry showed a 629-pixel document on a 390-pixel viewport, driven by offscreen table links despite visual clipping. Containment keeps those descendants within their dedicated scroll region.
- Validation: The diagnostic run again passed 465 backend tests and 22 browser scenarios, isolating the same overflow. Local ESLint, TypeScript and production build passed for the fix; corrected hosted verification is pending.
- Limitations: No global page clipping or weakened width assertion was introduced. Human review and owned-pilot App/deployment acceptance remain pending; zero additional AI calls.

## 2026-10-25T02:21:52+05:30 — Diagnose hosted mobile comparison overflow

- Changed: The existing mobile browser assertion now records bounded element geometry and a full-page screenshot before checking viewport containment.
- Why: Hosted run 40131342232 passed 465 backend tests and 22 browser cases, but exposed horizontal overflow in the comparison flow. The width assertion remains strict; the new evidence will identify the responsible element.
- Validation: Frontend ESLint and TypeScript passed. Restarted local services served all three report formats from saved evidence; 5 audits, 3 admissions and 6 AI reservations were preserved.
- Limitations: Mobile acceptance remains failed pending diagnosis/correction and a hosted rerun. No production data, quota or AI requests were changed; human review pending.

## 2026-10-25T02:08:47+05:30 — Compare saved evidence, export reports and inspect JSON-LD

- Changed: Added free same-origin saved-audit comparisons, Markdown/CSV/JSON report downloads, bounded JSON-LD diagnostics and accessible dashboard controls. Generated API contracts and proxy routes include the new interfaces.
- Why: Users need to inspect changes over time and share evidence without rerunning a crawl or paying for more AI. New analysis records rules version 2; historical snapshots and scoring version 1 remain intact.
- Safeguards: Incomplete, blocked, truncated or unfinished analysis never proves resolution. Score changes require matching versions/formulas and identical complete assessed coverage. Reports omit private source/configuration, reject exports over 1 MiB and neutralize spreadsheet formulas. Raw JSON-LD is discarded; diagnostics do not establish rich-result eligibility.
- Validation: 465 backend tests passed in 45.96 seconds; Ruff, frontend ESLint/TypeScript, seven proxy tests, production build and credential/history/link checks passed. Separate standards/spec reviews corrected unfinished-analysis absence and truncated JSON-LD UI evidence. Eight new browser cases await the authorized GitHub-hosted run.
- Limitations: No new live audit or paid request was made; existing counters were preserved. Pilot App setup, exact-patch review, manual deployment and human review remain pending.

## 2026-10-25T01:56:07+05:30 — Keep indexing evidence complete or explicitly unknown

- Changed: Unified the ten-entry robots bound for HTML metadata and response headers; overflow now marks the field truncated instead of silently dropping extra directives.
- Why: A later noindex directive could be omitted without warning, allowing the retained prefix to appear complete during live verification.
- Validation: Reproduced both failures before the fix; 41 extraction/workflow tests and Ruff passed. Separate standards and functional reviews found no remaining issue.
- Limitations: Evidence beyond the bound is intentionally unavailable and blocks metadata verification; no new network or AI requests. Human review pending.

## 2026-10-25T01:47:01+05:30 — Record passing hosted v2 validation

- Changed: Updated README, verification and submission records for source `fbb94e2046212ce26469a46850d303bae92b387a`; all implementation and test corrections are pushed without rewriting history.
- Validation: GitHub run `40128792918` passed 356 backend tests, 34 AST tests, seven validator tests, seven proxy tests, 15 Chromium scenarios, lint/type/build and contract/credential checks. Hosted mobile review screenshot inspected. Restarted local API/dashboard serve v2; five audits, three admissions and six AI reservations remain preserved.
- Limitations: The pilot App is not configured; owner workflow installation, exact-patch publication approval, manual merge/deploy and live verification remain required. Human review pending. This is a documentation-only checkpoint; no additional AI calls or counter resets.

## 2026-10-25T01:42:32+05:30 — Align hosted browser assertions with accessible controls

- Changed: Browser scenarios select the URL searchbox, distinguish application errors from Next.js's route announcer, and wait for the AI control to finish initializing before opting out.
- Why: Hosted Chromium passed 10 scenarios and exposed five selector/synchronization failures in previously unexecuted test code; backend 356 tests and static/build checks passed on Linux.
- Validation: Reviewed each failure against its rendered locator log; frontend lint/type checks rerun. A fresh hosted run verifies the corrected cases.
- Limitations: Pilot App installation and human deployment remain pending. No paid requests or user counter resets.

## 2026-10-25T01:38:44+05:30 — Isolate fake-provider tests from CI runtime settings

- Changed: Test bootstrap enables mock AI contract paths while still masking credentials and disabling dotenv. Browser services retain their explicit AI kill switch.
- Why: The first v2 hosted run inherited `SEOPILOT_AI_ENABLED=false` and stopped at 16 fake-provider assertions before browser checks; 340 other tests passed.
- Validation: Full suite passed 356 tests in 42.59 seconds with the same disabled parent setting; Ruff and diff checks passed. No production behavior, quota or credential value changed.
- Limitations: Hosted browser acceptance and owned pilot remain pending. Human review pending.

## 2026-10-25T01:33:36+05:30 — Complete the v2 dashboard and delivery documentation

- Changed: Added project/App onboarding, audit/source mapping, metadata preparation, escaped diff/download, exact-hash draft-PR consent, checks/history, deployment acknowledgement, live verification, finding dispositions and immediate source deletion. Added 15 hosted browser scenarios, isolated credentials, pinned validation tooling and orphan temporary-file cleanup. Updated setup, architecture, verification and pilot/submission records.
- Why: Make the reviewed-change workflow usable while preserving human publication/merge/deployment decisions, audit history and spending limits.
- Validation: Full backend suite 355 passed in 42.60 seconds; six subsequent retention tests passed including the orphan-file regression. 34 AST, seven validator and seven proxy tests passed. Ruff, ESLint, TypeScript, production build and pre-documentation credential/history checks passed. Copied migration retained 5 audits, 7 pages, 26 findings, 29 recommendations, 0 decisions, 3 admissions and 6 AI reservations; original counters stayed unchanged. Independent reviews corrected stale/null edits, truncation, disposition selection and recovery/retention issues.
- Limitations: Hosted 15-scenario browser result awaits push/CI. A scenario-listing invocation unexpectedly started the local runner and was immediately stopped; no accepted local browser result is claimed. The portfolio pilot still needs App settings, owner workflow, inspected draft PR, manual merge/deployment and live verification. Human review and organizer submission remain pending; no additional paid AI calls or counter resets.

## 2026-10-25T01:26:56+05:30 — PR publication, recovery and deployment verification

- Changed: Added queued proposal/publication API and worker stages, precise patch binding/export, duplicate-safe branch/commit/PR reconciliation, bounded hosted artifact validation, manual post-deployment verification and stable rule/URL/field comparisons. Added finding dispositions without altering historical scores, targeted crawler mode, versioned scores, 10-minute polling windows and immediate cancellation/source deletion.
- Why: Turn explicit approval into a reviewable draft PR and distinguish validated source, merge, deployment and actual live metadata.
- Validation: 352 backend tests passed before the final polling/truncation safeguards; 30 integrated workflow fixtures and 24 artifact tests cover uncertain writes, forged identities/results, source privacy, quotas and failed/reduced live coverage. Seven proxy tests passed; Ruff passed. Final safeguard checks continue in the product milestone.
- Limitations: Live App installation, owner-installed workflow, manual review/merge/deployment and pilot acceptance remain pending. No target repository scripts ran locally and no additional AI requests were made. Human review pending.

## 2026-10-25T01:18:15+05:30 — Trusted static metadata adapter

- Changed: Added `repository-tools/` pinned TypeScript AST parser and isolated Python adapter. Exact range edits preserve page content and unrelated metadata; static inherited values can receive page overrides.
- Why: Generate predictable title/description changes without code generation, extra AI calls or local execution of target repositories.
- Validation: 34 Node tests and 21 Python adapter tests passed, including Unicode/escaping, inheritance, dynamic/client/template refusals and a source-execution/environment canary. Ruff passed.
- Limitations: TypeScript `.ts/.tsx` App Router only; uncertain metadata and routes require manual work. Human review pending; pilot deployment remains unverified.

## 2026-10-25T01:15:22+05:30 — V2 connection and persistence foundation

- Changed: Added GitHub App authorization, repository-scoped in-memory tokens, v3 SQLite project/fix/event/publication/disposition storage, contracts and safe environment examples. Existing audit history and counters are preserved.
- Why: Establish credential and persistence boundaries before exposing repository writes.
- Validation: Existing baseline 207 backend tests passed; 66 focused GitHub/persistence tests passed with fresh databases and injected transports. No live GitHub App or OpenAI calls used.
- Limitations: API/UI integration and pilot acceptance follow in later milestones. Human review pending.

Record each meaningful project change during the event, newest first. Update this file in the same commit as the change. Use a real timestamp with timezone, for example `YYYY-MM-DDTHH:MM:SS+05:30`.

## Event build log

## 2026-10-25T00:18:56+05:30 — Verify real SEO evidence and correct verified AI TLS trust

- Changed: Ran bounded live Python.org and Example.com audits with the user's existing key, independently checked raw metadata/headings and score arithmetic, verified live quota/deduplication/persistence/secret boundaries, and recorded exact results. Matched AI TLS to the crawler's verified system trust store, improved sanitized connection failure guidance and isolated pytest from real credentials/dotenv.
- Why: Verify actual optional AI behavior and SEO evidence, fix a reproduced SDK certificate-trust failure without weakening TLS, and prevent future routine tests from spending the developer's credits.
- Validation: TLS regression failed before correction; 207 offline backend tests and Ruff passed afterward. Python's three-page sample scored89 with three evidence-reviewed AI suggestions. Example scored82; authenticated model lookup and post-fix generation returned success, while its spent lifetime review budget correctly withheld suggestions. Fourth admission429, duplicate reuse and forged-header403 passed across restart. No credentials appeared in checked responses or Git.
- Limitations: Three live audit slots and six conservative AI reservations were consumed, including failed/local diagnostics; no counters were reset. Full Example generation/review was not repeated after its lifetime limit. Browser verification remains blocked; ranking performance and public hosting are unverified. Human review pending.

## 2026-10-24T18:25:46+00:00 — Record atomic publication and successful hosted verification

- Changed: Recorded implementation commit `3a90c3cd24662eb11bd6ea1067ea7a07a6c754f9`, atomic publication of both security/UI commits, and successful GitHub Actions run 40120505329 in README, verification and submission notes.
- Why: Preserve a stable implementation/CI reference and distinguish observed hosted results from the earlier pending record.
- Validation: Atomic dry run and push succeeded; remote `main` matched local HEAD and the working tree was clean before this documentation checkpoint. GitHub reports hosted Checks success. Private environment files remain ignored/untracked. No application source changed here.
- Limitations: Hosted action-runtime/runner migration notices remain non-blocking; previous browser, live-AI and public-hosting limits remain. Human review is pending.

## 2026-10-24T18:18:49+00:00 — Show audit allowances and automate offline checks

- Changed: Added dashboard allowance/reset/shared-AI information, AI opt-out, exhausted-quota controls, duplicate-reuse notices and limited-AI state; extended browser scenario source and added a read-only GitHub Actions validation workflow.
- Why: Make server spending protections understandable before submission and catch credential/contract/regression mistakes on future pushes without using paid AI.
- Validation: ESLint, TypeScript and production build passed with the integrated UI; six Node proxy tests passed. Backend suite remains 205 passing. Repository working/staged/history checks passed before the server milestone commit. Browser scenarios were not executed and the hosted CI result has not yet been observed.
- Limitations: Managed browser-origin denial still blocks desktop/mobile rendered verification. No live AI, hosting or human review is claimed. The server enforces quotas independently of UI controls.

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

## Template setup — 10 October 2026

- Changed: Added the event README, rules, agent guide, change log, AI usage record, submission checklist, Git ignore rules, and pull request checklist.
- Why: Give participants a consistent starting point for event rules, basic coding patterns, documented changes, and regular commits.
- Validation: Checked local Markdown links, event detail consistency, required documents, and diff whitespace before publishing.
- Limitations: Documentation scaffolding only; no participant project, application, or working demo is included. GitHub publication and template status are verified separately after creation.
