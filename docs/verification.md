# Verification and delivery record

Updated 25 October 2026 (IST), using Node 22.17.0, Python 3.13.6, Next.js 16.4.3 and committed lockfiles. Historical real SEO/AI observations remain in the [bounded live record](live-validation-2026-10-25.md).

## Portfolio report and dashboard DNS failure

Final hosted check at 2026-10-25T07:38:42+05:30: exact source [`57bcd9b`](https://github.com/thanushreesuresh/SEOpilot/commit/57bcd9b5ff5ced20b093c22fd780dc0687e0071f) completed [run 40153134015](https://github.com/thanushreesuresh/SEOpilot/actions/runs/40153134015) successfully. The job recorded 637 backend cases in 26.09 seconds and 51 browser scenarios in 35.6 seconds, including both new unknown-result/keyboard viewports. AST/validator/proxy/build-guard tests, Ruff, ESLint, TypeScript, production build, generated-contract drift and credential/history checks passed. Browser evidence is fixture-based against `next dev`; local rendered inspection remains blocked, and a production build alone does not establish production rendering. No local build was run over the live dashboard's assets. Human review remains pending.

Runtime follow-up at 2026-10-25T07:37:02+05:30: after the owner explicitly requested stopping the backend, the exact verified SEOPilot listener was stopped and the API restarted with the saved resolver setting. A fresh `POST /api/audits` through the normal Next proxy returned 202 with reuse false, then audit `b5bfa1da-0d6a-4a63-9ae3-851c0b5f509b` finished partial with eight HTML pages assessed, 12 findings and score 84/100. Its saved discovery records configured Google HTTPS DNS. The PDF remains unchecked and retained text truncated; the score is not a claim of deployment improvement. The shared AI allowance stayed 14, with AI disabled throughout. Markdown and JSON reports were saved outside the checkout as `portfolio-dashboard-audit-2026-10-25` files. This proves normal API admission/worker/report delivery with real website evidence, not rendered browser interaction. The API restart blocker is resolved; the local production frontend has not been rebuilt for the new failure controls.

At 2026-10-25T07:33:37+05:30, the owner's requested report was generated first using the developer CLI with `--dns google`, 15-page/depth-two bounds and AI disabled. Audit `b71fab35-f2dc-40f7-8202-300b3cd95af4` assessed eight HTML pages across nine observations, found 12 issues and scored 84/100. Duplicate title/description observations cover the eight pages; missing canonicals cover eight pages; inspected robots/sitemap locations confirmed absence. The PDF was unchecked and retained text hit extraction limits, so the result remains partial. Markdown/JSON exports were saved outside the checkout in Downloads/SEOPilot-Reports and the Markdown file was queued for opening in Codex. No live AI calls or repository writes were needed.

The failed dashboard audit `9620bf92-357e-4c10-a124-eecc27807e6c` had zero assessed pages because robots retrieval stopped at DNS validation. A live resolver probe reproduced public IPv4 records mixed with restricted NAT64 64:ff9b::/96 results from system DNS; validation failed before a destination connection. The explicit Google resolver returned public addresses and produced the real report. The fix configures that existing resolver for dashboard workers through server-only `SEOPILOT_CRAWL_DNS=google`, preserving default system resolution and rejecting unknown settings, restricted answers, provider failures and off-origin redirects. No automatic fallback was added.

The regression command initially failed four cases on absent configuration support. After the fix, the full backend suite passed 636 cases in 99.89 seconds (one upstream Starlette deprecation warning); after the final explicit-override/provenance case, all five targeted cases passed in 5.32 seconds. They drive API admission, the real worker/crawler/rules/storage and saved Markdown export with injected DNS/transport, proving mixed results still prevent connections and paid calls remain zero. Ruff and frontend lint/type checks passed. Two new hosted desktop/mobile scenarios cover unknown-result text, preserved failure reasons, report availability and keyboard navigation to Pages. Build/browser results are pending, and local rendered inspection remains denied.

Google resolution was selected only in ignored backend/.env without printing credentials. Automatic approval review rejected the verified backend restart as blocked by policy, with no further reason supplied; a manual restart is pending. Production frontend changes require the documented stop/build/start cycle. Existing failed records and original scores are retained. No claim is made that the running dashboard worker has loaded this change, that all pages are assessable, or that portfolio SEO has been deployed or improved. Human review pending.

## Stylesheet delivery and stale dashboard process

Follow-up at 2026-10-25T07:19:44+05:30: after the old listener stopped and port 3000 was free, the normal `npm run dev` command started successfully. Server-level checks returned HTTP 200 for the stylesheet (with dashboard rules), all 17 referenced JavaScript files, and `/api/usage` plus `/api/audits`. The extra forwarded port argument had not survived the PowerShell/npm wrapper, so README recovery now uses the verified normal command. The open browser requires a hard refresh; local rendered access remains denied and is not claimed as verified. Framework-generated local instruction/type-file changes were excluded from this documentation commit.

Source [`9f6dbd3`](https://github.com/thanushreesuresh/SEOpilot/commit/9f6dbd31a5c48ebe15516ed53afd5cddfe6b2db1) passed [hosted run 40151593481](https://github.com/thanushreesuresh/SEOpilot/actions/runs/40151593481): 623 backend cases in 24.20 seconds, 48 browser scenarios in 35.1 seconds, two build-guard cases, helper/proxy/static checks, production build, generated-contract drift and credential/history checks. Both new asset/navigation viewports passed; existing desktop discovery and mobile sample fixture screenshots from this exact run were inspected. Browser scenarios run against `next dev`; production rendering is not established merely by the successful production build. Standards and specification reviews found no actionable issues in the implementation.

At 2026-10-25T07:08:23+05:30, the user's unstyled screenshot was traced to the local production server returning HTTP 200 HTML with a stylesheet reference returning HTTP 404 and one failed JavaScript asset. The source imports its existing stylesheet correctly, and a newer CSS asset exists on disk. Process inspection identified the project-specific `next start` listener; it was not terminated. The user received exact manual stop/start instructions because an earlier automatic approval review blocked dashboard restart.

The normal build now checks loopback port 3000 and optional PORT before spawning Next. An occupied port or unverifiable check refuses the build with actionable guidance and leaves the running server alone. Two unit cases exercise a real TCP listener, unchanged BUILD_ID, a closed port and invalid input. Both passed, as did frontend lint/type checking. New desktop/mobile browser cases verify actual CSS response/MIME type, font/reset/layout, loading completion, overflow, keyboard-driven history navigation and runtime/console health. CI runs the guard tests before building.

Local Browser access was rejected by the saved origin policy, so no local rendered/screenshot acceptance is claimed and no browser fallback was attempted. Hosted production build/browser results and manual restart remain pending at this checkpoint. The guard is an initial port check, not a process lock; undeclared custom ports, direct Next commands and a listener starting after the check remain operator responsibilities. No credentials, audit quotas or portfolio state changed.

## Real portfolio audit and approved draft PR

Hosted follow-up at 2026-10-25T06:48:36+05:30: implementation source [`e5928afa66071f25ff44e06b6c62cf8d6668db57`](https://github.com/thanushreesuresh/SEOpilot/commit/e5928afa66071f25ff44e06b6c62cf8d6668db57) passed [run 40149886193](https://github.com/thanushreesuresh/SEOpilot/actions/runs/40149886193): **623 backend tests in 31.08 seconds and 46 browser scenarios in 41.2 seconds**, 34 AST and seven validator/proxy cases each, Ruff/ESLint/type checking, production build, generated-contract drift and credential/history checks. This is SEOPilot's fixture/implementation CI; the portfolio's owner workflow and live deployment gates remain unresolved. Frontend source is unchanged; no new visual inspection is claimed.

At 2026-10-25T06:41:05+05:30, the [real pilot record](portfolio-pilot-2026-10-25.md) documents eight assessed HTML pages, 12 evidence-backed observations, partial coverage and score 84. An explicitly approved exact metadata patch was published through the installed App as [portfolio draft PR #1](https://github.com/thanushreesuresh/thanushree-portfolio/pull/1), head `512001fa1e26a77eb37cddee59f2808345d07306`; its single-parent, single-file remote commit was verified. Vercel reports the preview Ready, while the protected preview audit stopped on an off-origin redirect. The configured owner workflow is missing; no rendered/production verification or score improvement is claimed.

The user clarified that public admission limits do not apply to local developers. The terminal-only command makes real, AI-disabled runs in existing history without altering admissions or exposing an HTTP exemption. Default DNS still refuses the locally synthesized restricted NAT64 results; the explicitly selected Google DoH resolver checks both families, rejects restricted/incomplete replies and retains pinned transport. Public admission rows remained three and paid reservations six. Three new developer audit records (including the honest failed DNS and preview attempts), the project mapping, proposal/checkpoints and one approved publication reservation were added. Earlier records and counters were not reset.

Checks: 623 backend tests passed in 68.99 seconds after the cancellation correction, plus 34 AST, seven validator, seven proxy, repository Ruff and frontend lint/types. Initial developer/DNS tests failed before their modules existed; the full suite then passed. One lint invocation from inside backend incorrectly applied that folder's rules to the existing scripts directory; the documented root Ruff command passed. Existing upstream Python/Node warnings remain. Both independent review axes are clear after the developer processor was changed to honor dashboard cancellation. Hosted source/browser rerun remains pending at this checkpoint.

## Installed App live connection check

At 2026-10-25T06:23:12+05:30, the owner-configured App authenticated to GitHub and returned one selected-repository installation with exactly Metadata/Actions read and Contents/Pull requests write. Exactly one eligible repository was returned: `thanushreesuresh/thanushree-portfolio`. Scoped authorization and reading `main` passed at `193eb61222d1ee695077cdbff095c50de0ca1db1`.

Using a fresh temporary SQLite database, disabled AI and no audit worker, the real `/api/github/connection` route returned `ready`; project creation/history passed against that repository and user-confirmed production origin. The trusted AST helper read authenticated sources as data, prepared an illustrative `app/page.tsx` title override and refused the unsupported dynamic route. Source stayed in memory, no proposal was retained and no target code was executed. No OpenAI request, repository write, publication, merge or deployment occurred. Read-only before/after checks confirmed the operator's audit/decision/admission/AI counters were unchanged. The ignored environment file and external key path were checked without printing secrets.

Command: from `backend/`, `../.venv/Scripts/python.exe -m pytest tests/test_github_app.py tests/test_optional_github_setup.py tests/test_fix_storage.py tests/test_fix_workflow.py -q` — **116 passed in 34.76 seconds**, with the existing Starlette/httpx deprecation warning. These fixture tests disable dotenv/live credentials; the separate live probe used the App credentials only. This documentation-only checkpoint does not repeat the earlier full hosted suite.

Remaining: the running local backend still exposes an older unconfigured response and requires manual restart. The portfolio's `seopilot-validation.yml` lookup returned not found. Owner workflow installation, saved project mapping, current live-audit evidence, wording/diff review, exact-patch publication approval, hosted checks, manual merge/deployment and live verification remain pending. Human review is pending.

## Genuine legacy upgrade and release-readiness checkpoint

At 2026-10-25T05:35:12+05:30, source **`6231133bbb465f3fba2b0f7c2b69601c07df09d9`** passed the [complete hosted run](https://github.com/thanushreesuresh/SEOpilot/actions/runs/40145002773). This later documentation checkpoint changes no implementation.

| Upgrade check | Observed result |
| --- | --- |
| Complete backend suite | **598 passed**, 59.25 seconds locally and 31.54 seconds on GitHub; existing upstream TestClient warning remains |
| AST / hosted-validator / authenticated-proxy checks | **34 / 7 / 7 passed** on GitHub |
| Ruff, ESLint, TypeScript, production build | Passed on GitHub; changed backend suite and Ruff passed locally |
| Generated-contract drift and credential/history checks | Passed on GitHub; local working/staged and ignored-private-path checks passed |
| Hosted Chromium | **46 passed** in 49.4 seconds; frontend source unchanged by this backend follow-up |
| Original database, read-only | Still 5 audits, 7 pages, 26 issues, 29 recommendations, 0 decisions, 3 admissions and 6 AI reservations |
| Additional live AI requests / website requests / pilot repository changes | **0 / 0 / 0** for this iteration |

The release audit found that the previous migration test created a current-schema database and only lowered its version number, without creating a decision. It now has an honest reopen-test name. Fifteen new cases start with the actual pre-repository-workflow schema from source `3a90c3c`, seed synthetic old payloads, timestamped rejection/approval events, quota salt, admission and AI reservations, and only then initialize the current Store. Assertions preserve every original row/payload, history, score, decisions, salt, charges and new project mapping, including idempotent approval and subsequent review.

Four new cases first reproduced an admission bug: pre-v2 fingerprints omitted `verification_urls`, so adding the empty list in a later release stopped identical legacy requests from being reused. Normal crawls now match either known format without rewriting admissions. Tests verify active/recent reuse, API `X-Audit-Reused`, reuse even with exhausted daily quota, and rejection of reuse for changed peer/context/options/AI opt-out/verification scope or expired completed evidence. Separate standards/specification reviews found no actionable issues in the immutable patch.

The [release-readiness report](release-readiness.md) maps the approved v2 clusters to inspected source and substantive test assertions. A separate pinned public-source probe checked portfolio commit `193eb61222d1ee695077cdbff095c50de0ca1db1`: fetched page/layout text matched its Git blob hashes, the production AST adapter added only a home-page title override while preserving description/layout, and a dynamic project route was refused. No portfolio imports/config/build/scripts were executed; the temporary source input was deleted. The observed root lacks the owner validator and an ESLint configuration for its declared `next lint` script. Owner lint preparation is recommended from the version-matched official documentation; no actual pilot lint/build failure is claimed.

The owner confirmed that the GitHub App is not yet set up. No live credentials were read or printed, no original counters reset, and tests use fresh databases with live credentials disabled. Local services were not restarted and are not acceptance evidence for this source. Automatic approval previously rejected dashboard restart as “blocked by policy”; manual restart remains required. App installation/configuration, owner workflow, reviewed exact-patch publication, human merge/deployment, live verification and human review remain pending. Static source compatibility and passing SEOPilot fixtures do not satisfy that real release gate.

## Optional GitHub setup isolation checkpoint

At 2026-10-25T05:11:33+05:30, source **`dca6465843d8565429fa39e6d2a8e036aa33cb83`** passed the [complete hosted run](https://github.com/thanushreesuresh/SEOpilot/actions/runs/40143543032). This later documentation checkpoint changes no implementation.

| Setup-isolation check | Observed result |
| --- | --- |
| Complete backend suite | **583 passed**, 51.25 seconds locally and 30.84 seconds on GitHub; existing upstream TestClient warning remains |
| AST / hosted-validator / authenticated-proxy checks | **34 / 7 / 7 passed** locally and on GitHub |
| Ruff, ESLint, TypeScript, production build | Passed locally and on GitHub |
| Generated-contract drift and credential/history checks | Passed on GitHub; local working/staged and ignored-private-path checks passed |
| Hosted Chromium | **46 passed** in 51.2 seconds, including two new invalid-setting guidance/audit-access/mobile-recovery scenarios |
| Original database, read-only | Still 5 audits, 7 pages, 26 issues, 29 recommendations, 0 decisions, 3 admissions and 6 AI reservations |
| Additional live AI requests / pilot repository changes | **0 / 0** for this iteration |

The initial ten regression cases failed before implementation. Twelve new offline cases now verify malformed IDs/owners, failed home expansion, discarded rejected values, partial setting presence, valid/missing configurations, unrelated programming errors propagating, blocked project connection, real runner analysis using fixture pages, persisted queue recovery, historical findings/scores/decisions/counters after restart and successful disconnect after settings become invalid. Tripwires reject GitHub requests and private-key reads during these cases; private canaries stay out of public responses and logs. The strict parser remains available; runtime startup/disconnect isolate only its expected optional configuration failures.

Separate standards/specification reviews found no actionable issues in the immutable patch. Hosted cases confirm auditing is accessible while the App error is visible, onboarding stays disabled, mobile guidance fits the viewport and keyboard refresh recovers after a simulated corrected setup. The final 390-pixel screenshot was inspected: the correction heading, fixed guidance and presence-only checklist are readable and contained, with no raw credential/path values. The development indicator remains an existing capture artifact. This fixture recovery does not establish real App access or remove the documented restart requirement.

No live credentials were read or printed, no original counters reset, and tests use fresh databases with live credentials disabled. Local services were not restarted and are not acceptance evidence for this source. Automatic approval previously rejected dashboard restart as “blocked by policy”; manual restart remains required. Real App setup, owner workflow, exact-patch pilot approval, human merge/deployment, live verification and human review remain pending. Historical checkpoints below accurately describe earlier source behavior; the earlier fatal optional-settings limitation is fixed by this source.

## GitHub connection diagnostics checkpoint

At 2026-10-25T04:57:18+05:30, source **`38158868473a40883d85ad84d1e43362cefe8a40`** passed the [complete hosted run](https://github.com/thanushreesuresh/SEOpilot/actions/runs/40142551431). This later documentation checkpoint changes no implementation.

| Connection check | Observed result |
| --- | --- |
| Complete backend suite | **571 passed**, 46.75 seconds locally and 30.36 seconds on GitHub; existing upstream TestClient warning remains |
| AST / hosted-validator / authenticated-proxy checks | **34 / 7 / 7 passed** locally and on GitHub |
| Ruff, ESLint, TypeScript, production build | Passed locally and on GitHub |
| Generated-contract drift and credential/history checks | Passed on GitHub; local working/staged and ignored-private-path checks passed |
| Hosted Chromium | **44 passed** in 48.4 seconds, including eight new connection-state, legacy-response and mobile keyboard cases |
| Original database, read-only | Still 5 audits, 7 pages, 26 issues, 29 recommendations, 0 decisions, 3 admissions and 6 AI reservations |
| Additional live AI requests / pilot repository changes | **0 / 0** for this iteration |

The 22 new offline cases verify all combinations of setting presence without reading a PEM, incomplete setup without a GitHub request, ready versus empty repository lists, fixed guidance for known/unknown provider failures, recovery, revocation, an unreadable key and private canaries absent from responses/logs. The initial 21 cases failed before implementation. Separate standards/specification reviews found no actionable issues in the immutable patch. The endpoint remains bounded by the existing GitHub client limits; a refresh may authenticate to GitHub but changes no repository and makes no OpenAI call.

Hosted cases verify disabled onboarding for authentication/access/rate/unavailable/empty/unknown states, legacy responses failing closed without a page error, setting presence and timestamps, a pending refresh clearing stale onboarding access, repeated keyboard activation remaining disabled, error recovery and missing-setting recovery. The final 390-pixel screenshot was inspected: the checklist and its 12-pixel explanation wrap within the card, values/key paths are absent, and the recovered onboarding form stays within the viewport. The development indicator remains an existing capture artifact. These fixture results do not establish a real App connection.

Invalid App ID/owner formats still stop backend startup with fixed validation errors; the checklist checks presence and GitHub access rather than replacing startup validation. No live credentials were read or printed and no original counters reset. Tests use fresh databases with live credentials disabled. Local services were not restarted and are not acceptance evidence for this source. Automatic approval previously rejected dashboard restart as “blocked by policy”; manual restart remains required. The owned pilot still requires App installation/configuration, the owner workflow, exact-patch approval, human merge/deployment, successful live verification and human review.

## Revision-aware sample checkpoint

At 2026-10-25T04:42:07+05:30, source **`1482a5ca227acf9e3260fc3708b3a2d2d1a76ce2`** passed the [complete hosted run](https://github.com/thanushreesuresh/SEOpilot/actions/runs/40141578038). This later documentation checkpoint changes no implementation and expands the owner-requested GitHub App setup instructions.

| Sample check | Observed result |
| --- | --- |
| Complete backend suite | **549 passed**, 63.61 seconds locally and 26.03 seconds on GitHub; existing upstream TestClient warning remains |
| AST / hosted-validator / authenticated-proxy checks | **34 / 7 / 7 passed** locally and on GitHub |
| Ruff, ESLint, TypeScript, production build | Passed locally and on GitHub |
| Generated-contract drift and credential/history checks | Passed on GitHub; local working/staged/history and ignored-private-path checks passed |
| Hosted Chromium | **36 passed** in 29.4 seconds, including revision provenance, preserved historical decisions/allowances and mobile keyboard error/retry cases |
| Original database, read-only | Still 5 audits, 7 pages, 26 issues, 29 recommendations, 0 decisions, 3 admissions and 6 AI reservations |
| Additional live AI requests / website writes | **0 / 0** for this iteration |

Offline cases verify legacy raw JSON is unchanged, revisions reuse samples beyond the history window and across concurrent stores/restarts, decisions survive reopening, forged revisions cannot select fixtures, invalid candidates fail closed, and the burst limit remains enforced without live quota or AI reservations. Markdown/CSV/JSON reports retain sample provenance. The final 390-pixel mobile screenshot was inspected: the revision disclosure wraps within the card, sample controls and evidence are visible, and viewport-containment and no-page-error assertions passed. The development indicator is an existing capture artifact.

Source `8b80716` passed 549 backend and 35 browser cases; the new mobile case failed before sending its sample request. Static trace inspection showed focus was attempted during initialization without waiting for the button to be enabled. The follow-up waits for enabled state and asserts focus before both Enter activations; all error/retry/history assertions remain. Separate standards/specification reviews found no actionable issues in the feature or correction patches. The final source above passes all 36 scenarios.

The owner requested GitHub App setup guidance. The expanded guide gives exact registration permissions, selected-repository installation, numeric App ID versus Client ID, a PEM path outside this OneDrive checkout, preserving the existing ignored dotenv, manual restart and sanitized troubleshooting. Registration and private-key screens were checked against official GitHub documentation; no App was created or configured by this documentation change.

No live credentials were read or printed, no original counters reset, and tests used fresh databases with live credentials disabled. Local services were not restarted and are not acceptance evidence for this source. Automatic approval previously rejected dashboard restart as “blocked by policy”; manual restart remains required. Owned-pilot App setup, owner workflow, exact-patch approval, human merge/deployment, live verification and human review remain pending.

## Explainable-score checkpoint

At 2026-10-25T04:12:30+05:30, source **`11f46b401b6ec84df8422bec8545890c737363c5`** passed the [complete hosted run](https://github.com/thanushreesuresh/SEOpilot/actions/runs/40139477667). This later documentation checkpoint changes no implementation.

| Score explanation check | Observed result |
| --- | --- |
| Complete backend suite | **534 passed**, 44.82 seconds locally and 27.62 seconds on GitHub; existing upstream TestClient warning remains |
| AST / hosted-validator / authenticated-proxy checks | **34 / 7 / 7 passed** locally and on GitHub |
| Ruff, ESLint, TypeScript, production build | Passed locally and on GitHub |
| Generated-contract drift and credential/history checks | Passed on GitHub; local working/staged/history and ignored-private-path checks passed |
| Hosted Chromium | **33 passed** in 37.5 seconds, including four new score scenarios and computed font-size/contrast checks for new and legacy explanations |
| Original database, read-only | Still 5 audits, 7 pages, 26 issues, 29 recommendations, 0 decisions, 3 admissions and 6 AI reservations |
| Additional live AI requests / website writes | **0 / 0** for this iteration |

Offline tests verify raw/capped totals, repeated/group rule deduplication, HTTP-error overrides, assessed-only denominators, nearest-even rounding, empty scores, snapshot persistence, unchanged scores after review decisions and safe Markdown/CSV/JSON exports. Hosted tests verify expansion, per-page deductions, navigation back to matching findings, mobile keyboard/viewport behavior, escaped rule text, legacy scores and excluded pages without a score. The final desktop/mobile screenshots were inspected: the scoped 12-pixel explanations use darker text and wrap within the viewport. The HTML canary remains text; no framework error overlay was observed. Existing development indicators and full-page placement of fixed navigation remain capture artifacts.

Source `270a6e5` passed 534 backend and 29 existing browser scenarios, but four new cases failed during sample setup. Static trace inspection confirmed HTTP 429 responses from redundant fixture-creation calls. Shared setup now reads existing sample history/detail and seeds only when absent, preserving the production burst limit. Source `47e2d1e` then passed all 33 browser cases. Screenshot inspection prompted the readability follow-up; independent specification review also caught the legacy paragraph's missing wrapper. Both final review axes found no remaining actionable issues, and the final run above passed the rendered size/contrast assertions for both branches.

No live credentials were read or printed, no original counters reset, and tests used fresh databases with live credentials disabled. The existing local services were not restarted and do not verify the new code. Automatic approval previously rejected the dashboard restart as “blocked by policy”; manual restart remains required. Owned-pilot App setup, exact-patch approval, human merge/deployment, live verification and human review remain pending. Diagnostic scores do not forecast ranking or traffic gains.

## Crawl discovery checkpoint

At 2026-10-25T03:40:59+05:30, source **`78dd569fb0a45b7afe7082b68afb8bece43500be`** passed the [complete hosted run](https://github.com/thanushreesuresh/SEOpilot/actions/runs/40137186217). This later documentation checkpoint changes no implementation.

| Discovery check | Observed result |
| --- | --- |
| Complete backend suite | **521 passed**, 65.57 seconds locally and 27.76 seconds on GitHub; existing upstream TestClient warning remains |
| AST / hosted-validator / authenticated-proxy checks | **34 / 7 / 7 passed** locally and on GitHub |
| Ruff, ESLint, TypeScript, production build | Passed locally and on GitHub |
| Generated-contract drift and credential/history checks | Passed on GitHub; local working/staged/history and ignored-private-path checks passed |
| Hosted Chromium | **29 passed** in 33.2 seconds, including new desktop/mobile discovery, escaped evidence, keyboard expansion, legacy unknown and viewport-containment cases |
| Original database, read-only | Still 5 audits, 7 pages, 26 issues, 29 recommendations, 0 decisions, 3 admissions and 6 AI reservations |
| Additional live AI requests / website writes | **0 / 0** for this iteration |

Independent standards/specification reviews found no actionable issues in the immutable patch. New offline tests verify successful/absent/invalid/blocked/failed checks, immutable progress snapshots, request-budget reuse, bounded contracts, cancellation/restart retention, legacy defaults, report inclusion and guarded site-policy resolution in either comparison direction. Hosted desktop and 390-pixel mobile screenshots were inspected: evidence cards wrap within the viewport, the keyboard summary has visible focus, and the HTML canary renders as escaped text. The existing development indicator and full-page capture placement of fixed navigation are not framework error overlays.

The local services were not restarted, so their old runtime is not acceptance evidence for this code. The prior automatic approval rejection of restarting the dashboard remains in effect; use the documented manual restart steps. No live credentials were read or printed, no original counters reset, and tests used fresh databases with live credentials disabled. Owned-pilot App setup, exact-patch approval, human merge/deployment, live verification and human review remain pending.

## Cancellation checkpoint

At 2026-10-25T03:22:10+05:30, source **`da67735cbc92945e383b6c092e1c59025f2daba0`** passed the [complete hosted run](https://github.com/thanushreesuresh/SEOpilot/actions/runs/40135903810). This later documentation checkpoint changes no implementation.

| Cancellation check | Observed result |
| --- | --- |
| Complete backend suite | **498 passed**, 70.58 seconds locally and 27.31 seconds on GitHub; existing upstream TestClient warning remains |
| AST / hosted-validator / authenticated-proxy checks | **34 / 7 / 7 passed** on GitHub |
| Ruff, ESLint, TypeScript, production build | Passed |
| Generated-contract drift and credential/history checks | Passed |
| Hosted Chromium | **26 passed** in 32.7 seconds, including desktop/mobile cancellation, error/retry, history, keyboard and retained-page states |
| Original database, read-only | Still 5 audits, 7 pages, 26 issues, 29 recommendations, 0 decisions, 3 admissions and 6 AI reservations |
| Additional live AI requests / website writes | **0 / 0** for this iteration |

Separate standards/spec reviews found no actionable issues in the immutable feature and shutdown-follow-up patches. Tests cover every active cancellation stage, idempotency, origin/ID errors, restart durability, stale saves, worker continuation/shutdown, cancellation during fake AI generation/review, preserved reservations and fresh verification admissions. Thirteen reproduced live-verification evidence failures now pass. A later review reproduced cleanup errors swallowing server cancellation; three new cases verify shutdown and its cleanup race without leaking private exception-message canaries.

The first hosted run passed 495 backend tests and 23 browser cases, with three new selector failures. Corrected status-role/table-cell selectors passed all 26 on `f9368c9`; the final shutdown follow-up passed the complete 498/26 run linked above. The final hosted mobile screenshot was inspected for the incomplete-result disclosure, retained pages, report controls and viewport containment. Fixtures use fresh databases and disabled live credentials.

Local production processes have not been restarted for this milestone and are not acceptance evidence for it; the earlier automatic approval rejection of the dashboard restart still applies. Restart the backend and dashboard using README commands after stopping the old services. No original counter or private configuration was reset or printed. Human review and owned-pilot App/PR/manual-deployment acceptance remain pending.

## Saved-evidence improvement checkpoint

At 2026-10-25T02:38:32+05:30, source **`39b31e5dd58670b92b4bafcb83f2a995784323a9`** passed the [complete hosted workflow](https://github.com/thanushreesuresh/SEOpilot/actions/runs/40132659834). This documentation checkpoint does not change the verified implementation.

| Current check | Observed result |
| --- | --- |
| Complete backend suite | **465 passed**, 45.96 seconds locally and 24.32 seconds on GitHub; existing upstream warning remains |
| AST / validator / proxy checks | **34 / 7 / 7 passed** on GitHub |
| Ruff, ESLint, TypeScript, production build | Passed locally and on GitHub |
| Generated-contract drift and credential/history checks | Passed on GitHub; local working/staged checks also passed |
| Hosted Chromium | **23 passed** in 29.8 seconds, including desktop, 390-pixel mobile, keyboard and error states |
| Saved-data runtime smoke | Markdown, CSV and JSON reports served through the Next proxy; 5 audits, 7 pages, 26 issues, 29 recommendations, 0 decisions, 3 admissions and 6 AI reservations unchanged |
| Local rendered browser acceptance | None; origin policy remains denied |
| Latest local production process | Restart still required after rebuilding; automatic approval review rejected restart with only “blocked by policy”; stale stylesheet returned 404 in a read-only resource check |

New offline cases cover same-origin and mode constraints, grouped findings, failed/interrupted analysis, truncated/unknown coverage, version/formula changes, bounded exports, spreadsheet injection, public-history filtering and JSON-LD limits/grammar. Fixtures use fresh databases and disabled live credentials. No paid requests were made for this iteration.

Separate standards and specification reviews corrected two evidence gaps: failed/interrupted analysis cannot supply negative evidence, and clipped HTML cannot establish absence of JSON-LD. The first hosted browser runs passed 22/23 and exposed a 629-pixel document in a 390-pixel viewport. Comparison containment alone failed; review identified the unpositioned accessible history-column label. Positioning header cells fixed the strict width check without hiding page overflow, and keyboard horizontal table scrolling passed. The final hosted mobile screenshot was inspected; its Next development indicator is expected, and production compilation is checked separately.

Eight new browser cases cover report downloads/retries, comparisons/filters/versions, incomplete data and mobile keyboard/escaping states. No local browser pass is claimed. Historical v2 results below remain tied to their original source SHA. The API remains running; stop the existing Next process and run `npm --prefix frontend run start` to load the current production build. Human review and owned-pilot App/PR/manual-deployment acceptance remain pending.

| Check | Result at the v2 product checkpoint |
| --- | --- |
| Complete backend pytest suite | **356 passed** locally in 42.59 seconds and on GitHub in 23.45 seconds; one upstream TestClient deprecation warning |
| Retention safeguards | Included in the complete suite; orphan temporary-file cleanup and history beyond 100 runs verified |
| TypeScript AST helper | **34 Node tests passed** |
| Hosted validation harness | **7 Node tests passed** |
| Authenticated proxy | **7 Node tests passed** |
| Focused integration checks | 99 scoped checks and 32 workflow fixtures passed before the final full suite |
| Ruff, backend and scripts | Passed |
| Frontend ESLint and TypeScript | Passed |
| Next.js production build | Passed |
| OpenAPI/frontend contracts | Regenerated with current contracts |
| Credential/history/ignored-path checks | Passed without printing credentials before this documentation update |
| Copied-database migration | Preserved 5 audits, 7 pages, 26 issues, 29 recommendations, 0 decisions, 3 admissions and 6 AI reservations |
| Original user database | Read-only counts preserved 5 audits, 0 decisions, 3 admissions and 6 AI reservations; counters never reset |
| Hosted browser coverage | **15 passed** in 19.6 seconds; [successful full workflow](https://github.com/thanushreesuresh/SEOpilot/actions/runs/40128792918) on source commit `fbb94e2046212ce26469a46850d303bae92b387a` |
| Accepted local browser/screenshot result | None; local-origin policy remains denied |
| Owned pilot through PR, deployment and live verification | Pending App setup, owner workflow and human actions |

Backend fixtures use fresh databases and injected transports. Pytest disables dotenv loading and masks OpenAI/GitHub App credentials. Tests exercise the real API, worker, persistence, AST adapter, comparisons and decisions while replacing external GitHub/crawl transports. No target repository scripts ran locally and no additional OpenAI calls were made for v2.

Coverage includes revoked repositories, forged IDs, expired tokens/redaction, static routes/inheritance, dynamic/client/template refusals, Unicode/escaping, exact hashes, stale commits, forbidden edits, duplicate publication and uncertain-response reconciliation. Artifacts reject wrong workflow/commit/proposal/run identities, missing evidence and contradictory metadata. Live checks cover blocked/missing/truncated metadata, version mismatches, coverage loss, fresh admissions and historical scores. Source/environment canaries check private code is not executed locally or sent to OpenAI.

Independent review corrected null metadata edits, reused verification results, truncated metadata acceptance, latest-disposition selection, polling/retention behavior, interrupted-source deletion and browser assertion labels. The final local suite includes these safeguards; orphan temporary-file cleanup has its separate focused pass.

## Browser and hosted validation status

The repository Checks workflow passed all 15 Chromium scenarios on GitHub-hosted runners with disabled live credentials and a disposable database. Tests intercept external calls and cover ownership/onboarding, approved text, escaped diffs, exact publication consent, failed/missing CI, deployment acknowledgement, mobile keyboard/download/deletion, connection errors and existing audits. The hosted 390-pixel mobile review screenshot was inspected for readable controls, wrapped metadata and a contained diff. Browser checks use the Next development server; production compilation is checked separately.

The origin gate previously denied `http://localhost:3000` despite user approval and a reported permission change. During v2 command discovery, an npm invocation intended to list scenarios unexpectedly started the local runner; it was stopped immediately. No accepted local browser execution, screenshot or visual-fidelity result is claimed. The authorized acceptance route is GitHub-hosted CI.

The owner-installed pilot workflow builds/renders exact proposal commits. It has not run on the selected pilot because the three local GitHub App settings are not configured. Harness fixtures pass; a real App/PR/deployment result remains required.

## Historical observed results

- The [earlier hosted offline run](https://github.com/thanushreesuresh/SEOpilot/actions/runs/40120505329) passed for security/allowance commit `3a90c3c`; it did not include v2 browser coverage.
- Python.org sampling assessed three pages, found eight observations, scored 89 and produced three reviewed AI suggestions. Example.com assessed one page, found six findings and scored 82. Independent HTML/score checks matched those runs.
- Live model access and the TLS trust correction were verified. A later Example generation succeeded; its spent lifetime review allowance withheld suggestions. Reservations and failures are disclosed in the live record. Credentials were never printed or committed.
- Restart quotas, fourth-admission `429`, duplicate reuse, forged-identity rejection and persistence were observed. These are historical observations, not expected future results.

## Release acceptance and limitations

The user selected [thanushreesuresh/thanushree-portfolio](https://github.com/thanushreesuresh/thanushree-portfolio), serving [thanushree-portfolio-six.vercel.app](https://thanushree-portfolio-six.vercel.app/). Acceptance requires configuring/installing the App, installing the owner workflow, connecting the confirmed mapping, inspecting a proposal, explicitly creating its draft PR, passing hosted checks, manually merging/deploying and verifying the recorded live URLs. Merge alone does not prove deployment. No pilot PR, deployment, ranking gain or traffic improvement is claimed.

The app remains local/single-user. Hosting/authentication, Search Console, recurring audits and additional sources/frameworks remain deferred. The TestClient warning is not suppressed. Human review and organizer submission remain pending.
