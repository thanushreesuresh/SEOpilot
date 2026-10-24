# Verification and delivery record

Updated 25 October 2026 (IST), using Node 22.17.0, Python 3.13.6, Next.js 16.4.3 and committed lockfiles. Historical real SEO/AI observations remain in the [bounded live record](live-validation-2026-10-25.md).

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
