# SEOPilot

Evidence-based SEO audits and reviewed metadata fixes for websites you own. Audit a public website, review findings, prepare a precise Next.js title/description patch, then explicitly approve a draft GitHub PR. GitHub-hosted checks and a separate live audit verify the change after you merge and deploy. Optional OpenAI analysis adds contextual suggestions; deterministic audits and patch generation work without paid services.

## Local setup (Windows PowerShell)

Requires Node.js 22+ and Python 3.13+ with SQLite JSON-function support (verified locally with bundled SQLite 3.50.4). Run from the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e "backend[dev]"
npm --prefix repository-tools ci --ignore-scripts
cd frontend
npm ci
cd ..
```

Start the API in one terminal:

```powershell
.\.venv\Scripts\python.exe -m seopilot
```

Start the dashboard in a second terminal:

```powershell
cd frontend
npm run dev
```

Open [SEOPilot](http://localhost:3000). Keep both services on loopback. Use one API worker; this release is a single-user, single-computer application.

## Configuration

The backend reads process variables and an ignored `backend/.env`. Copy the safe template once if the local file does not already exist:

```powershell
if (-not (Test-Path backend/.env)) { Copy-Item backend/.env.example backend/.env }
```

Add your key only to `OPENAI_API_KEY` in **backend/.env** and restart the backend. Keep the committed example blank. Never use `NEXT_PUBLIC_*` for keys or put keys in frontend files. The selected API model is [`gpt-6-luna`](https://developers.openai.com/api/docs/models/gpt-6-luna); other model IDs are rejected to avoid accidental cost changes. No key is needed for crawling, rules or samples.

| Variable | Default / purpose |
| --- | --- |
| `OPENAI_API_KEY` | Blank; server-only credential you supply locally |
| `OPENAI_MODEL` | `gpt-6-luna`; fixed allowed model |
| `SEOPILOT_AI_ENABLED` | `true`; set `false` and restart for zero AI calls |
| `SEOPILOT_AI_DAILY_CALL_LIMIT` | `20`; global maximum requests per rolling 24 hours, configurable 0–100 |
| `OPENAI_MAX_OUTPUT_TOKENS` | `2500`; per-call ceiling, allowed 512–2500, including reasoning |
| `SEOPILOT_DB` | Optional SQLite path; default `backend/.data/seopilot.db` |
| `SEOPILOT_PROXY_TOKEN_FILE` | Usually blank; optional private absolute token path, set identically in both server process environments |
| `GITHUB_APP_ID` | Optional private App ID; required for repository connections |
| `GITHUB_APP_PRIVATE_KEY_PATH` | Server-only path to an ignored PEM file; never the key contents |
| `GITHUB_APP_OWNERS` | Comma-separated allowed repository owner logins |

For repository fixes, follow the [private GitHub App setup guide](docs/github-app-setup.md). Install the App on selected repositories with Metadata read, Contents write, Pull requests write and Actions read. Keep its private key outside Git. Repository-scoped installation tokens remain in server memory; neither credentials nor tokens are returned to the browser. Install the [validation workflow and harness](validation/README.md) yourself in the target repository before publishing.

The project workspace distinguishes missing settings, verified repositories, empty eligible installations, authentication errors, denied access, API limits and unavailable verification. Its checklist exposes only whether the three server settings are present, with the last check time and fixed troubleshooting guidance. Presence is not credential validation. **Connect a project** stays disabled until repositories are verified; a refresh clears stale setup access and disables repeat button activation while pending. Older API responses remain unverified until the backend is restarted. Invalid App ID/owner formats or a key path whose home directory cannot be resolved disable only repository integration: the dashboard shows **Settings need correction**, while audits, history and decisions remain available. Correct the local settings and restart the backend; Refresh connection does not reload dotenv files.

The safe API entry point binds loopback, disables forwarded-header trust and access logs, and starts one worker. If invoking Uvicorn directly, include **`--no-proxy-headers --no-access-log`** and keep `--host 127.0.0.1`. Do not run multiple workers.

## Audit and spending protection

- Three accepted live audits per IP per **rolling 24 hours**. A fourth distinct audit receives `429` and `Retry-After` until the oldest admission expires. Counters persist across restarts and concurrent submissions. Admitted failures still count; invalid URLs and a full queue do not.
- Identical requests from the same IP reuse an active audit, or a completed result admitted within 15 minutes, without consuming another admission or triggering another AI stage. Context, crawl options and the AI opt-out are part of the match. Upgrades also recognize pre-v2 fingerprints for unchanged normal crawls; frozen-URL verification stays separate and saved admissions are never rewritten.
- At most two paid requests per audit: generation and review. Each must reserve a global allowance before calling OpenAI. Errors/timeouts retain their reservation, SDK retries are disabled, and unreviewed suggestions never publish. Output and UTF-8 input sizes are bounded. Reaching the cap preserves deterministic results.
- `GET /api/usage` exposes allowance/reset information; `allow_ai=false` opts an audit out of paid calls. The labelled sample uses no live quota or paid calls and repeated sample requests reuse its result. The real smoke-test command explicitly opts out of AI.
- The dashboard displays your remaining audits and next reset, the shared AI-call allowance, a no-AI option and duplicate-reuse notices. You can refresh the allowance after a reset; sample mode remains available when live quota is exhausted.
- The Next server derives client identity from its socket and authenticates it to the fixed loopback backend using a private generated token. Incoming forwarding/IP/token headers are discarded. The backend stores HMAC identities, groups IPv6 addresses by `/64`, and accepts stamped identity only from an authenticated loopback proxy.

Local browsers normally share one loopback allowance. A reverse proxy in front of Next also shares one conservative bucket; arbitrary forwarding headers are never trusted. Preserve the SQLite database and its quota salt when restarting: deleting/replacing it resets local counters. The proxy token is generated in ignored `backend/.data/proxy-token` and stays outside production bundles.

This release remains **local and single-user**. IP limits cannot stop a botnet by themselves; the global AI cap provides the additional spending boundary. Before public hosting, add authentication, audit ownership checks and a trusted edge with rate limits. For a monetary ceiling, also configure a dedicated OpenAI project with a restricted key and [project spend limits](https://developers.openai.com/api/docs/guides/spend-limits); application request counts are not billing telemetry. Provider spend-limit enforcement may have a short delay. Live `gpt-6-luna` access and a complete generation/review workflow have been tested; see the [bounded live verification record](docs/live-validation-2026-10-25.md).

No credentials are required for the labelled sample demo. Recommendation approval records content review. A separate **Create draft PR** action authorizes the exact inspected patch; merge and deployment remain manual.

Optional AI now uses structured generation followed by a separate evidence review. Invalid, unsupported or contradictory suggestions are withheld. Missing credentials, rate limits, timeouts and provider errors preserve deterministic findings. The sample audit parses bundled HTML through the production extractor and rules and clearly identifies curated suggestions as sample data.

## Stop an audit

Choose **Cancel audit** while a run is queued, crawling, analyzing, or reviewing. Cancellation records a server timestamp and retains the last saved evidence as an explicitly incomplete result. You can reopen it in history, export its report, compare its observed findings, and review retained rule-based recommendations. Missing findings in cancelled analysis remain unknown, and a cancelled run never supplies a comparable score or verifies a deployment.

Cancellation keeps the accepted audit admission and all existing AI reservations. A new run consumes a new admission; an AI request already in progress may still be billed. The worker checks durable cancellation every 300 ms while awaiting work, cancels the active asynchronous task and waits for cleanup before processing the next job. New paid-call reservations and stale worker saves are rejected after cancellation. Already-running network/provider work has cooperative cleanup; cancellation is not a provider-side refund or guaranteed immediate stop.

`POST /api/audits/{audit_id}/cancel` with JSON `{}` returns the retained `Audit`. Repeating it for an already cancelled run returns the same saved state; an ordinarily finished run returns `409`, an unknown UUID `404`, and a forged ID `422`. Existing origin, host and proxy protections apply. Queued cancellation and restart recovery are durable; the SQLite schema remains version 3, with no counter reset.

The cancellation milestone passed **498 backend tests and all 26 hosted browser scenarios** on source `da67735`, with frontend lint/type/proxy, AST/validator, contract/credential and production-build checks in the [complete hosted run](https://github.com/thanushreesuresh/SEOpilot/actions/runs/40135903810). Cleanup failures are logged without private exception text and cannot swallow server shutdown. Restart both local services to load the new code. The existing dashboard restart was previously blocked by automatic approval review, so the old local processes are not acceptance evidence for this milestone.

## Architecture

Next.js proxies allowlisted `/api/*` routes to FastAPI. One lifespan-managed asynchronous worker processes persisted audit and fix stages. Crawling, extraction, deterministic rules, AI analysis/review, GitHub access, static AST patching and storage remain separate modules. Pydantic defines the API contracts; frontend types are generated from OpenAPI. SQLite schema v3 preserves existing audits and counters while adding project connections, immutable proposals, execution events, publication reservations and finding dispositions.

Indexing evidence retains up to ten combined robots meta/header directives. Additional directives mark that field incomplete, so live verification cannot accept a matching prefix as the complete indexing policy.

Queued jobs survive restarts. Active jobs become interrupted, retain collected evidence, and can be rerun as a new audit. Network requests never hold database transactions. Audit history is local data and is ignored by Git.

## Saved comparisons, reports, and JSON-LD checks

Open **Audit history → Compare audits**, select **Earlier audit** and **Later audit**, then choose **Run comparison**. The selector uses the latest 100 saved audits. Both audits must be finished (`completed`, `partial`, `failed`, `interrupted`, or `cancelled`), use the same mode (live or sample), and have the same normalized origin, including scheme, hostname, and port. They must be different audits, and the baseline must have an earlier creation time. Comparing saved results starts no crawl, consumes no live-audit admission, and makes no AI calls.

Finding changes use rule ID, normalized URL, primary evidence field, and site/page scope rather than random finding IDs. The view separates added, persistent, resolved, and unresolved/unknown findings; filters by change status or URL; and shows shared, newly assessed, and removed URLs. Missing follow-up pages, blocked or unchecked evidence, truncated fields, unfinished analysis, or different rules cannot establish a fix. Newly assessed coverage is not reported as a regression. A score delta appears only when both audits have equal complete, untruncated coverage, matching rule/score versions and score formulas, available scores, and no unresolved/unknown findings. Historical scores stay unchanged; these comparisons do not measure rankings or traffic.

In an audit overview, choose **Report format → Markdown, CSV, or JSON → Download report**. Reports use saved findings and evidence, score/formula/version information, coverage, recommendations and their review status, decision/disposition history, and limitations. AI and sample suggestions retain their hypothesis and human-review labels. Reports are available after the audit finishes and make no new crawl or AI calls. Report content and its JSON response envelope are each bounded to **1 MiB**; oversized exports return an error rather than a clipped report. CSV uses standard quoting and prefixes formula-like cells, including whitespace-hidden prefixes, with an apostrophe. Markdown escapes source text. Exports exclude credentials and private repository source.

| Endpoint | Saved-data operation |
| --- | --- |
| `POST /api/audit-comparisons` | JSON body: `{"before_audit_id":"<earlier UUID>","after_audit_id":"<later UUID>"}`; returns finding changes, coverage, versions, and a nullable score delta |
| `GET /api/audits/{audit_id}/report/{format}` | `format` is `markdown`, `csv`, or `json`; returns `filename`, `media_type`, and `content` for download |

Open the **Pages** tab to inspect each page's JSON-LD summary. New HTML extraction retains declared type labels and bounded syntax/context observations; raw JSON-LD scripts are discarded. Inspection covers at most 10 blocks, 16 KiB per block, 64 KiB combined, nesting depth 32, 20 distinct type labels, and 50 observations. Limits and clipped HTML leave evidence incomplete; older saved pages without this inspection remain unknown. The checker does not fetch contexts, execute scripts, validate all Schema.org requirements, or establish rich-result eligibility. Missing or unfamiliar contexts receive review advice because custom vocabularies and fully qualified IRIs can be intentional.

New deterministic analyses record **rules version 2** for the JSON-LD diagnostics. Existing saved audits keep rules version 1 and their original findings and scores; score version remains **1**. A fresh audit is needed to collect the new evidence. Comparisons disclose version differences and withhold conclusions that the retained evidence cannot support.

## Crawl discovery evidence

New audits retain **Robots and sitemap checks** below coverage, including each inspected URL, final HTTP status, outcome and explanation. Expand **Inspect crawl discovery evidence** to see present, confirmed absent, blocked and unknown results, the recorded request-attempt count and effective minimum delay. Markdown, CSV and JSON reports include the same saved evidence. These additions reuse existing protected probes and make no additional network or AI requests.

At most one robots probe and three same-origin sitemap locations are retained. Sitemap inspection stops at the first recognized `urlset` or `sitemapindex` XML root; it does not validate every listed URL, find orphan pages, or confirm search-engine indexing. Unsafe/external declarations and candidate limits leave explicit notes; failed, invalid or robots-blocked responses remain unknown. An absent file alone is not a ranking penalty. Request counts include budgeted attempts, redirects and retries, including attempts that fail before connecting. Interrupted runs retain the last saved update, which may precede their final in-flight attempt. The normal 60-attempt ceiling, deadlines, robots rules, origin/DNS protections and spending limits remain in force.

Progress updates persist completed policy checks before content crawling, preserving them after cancellation or restart. Existing audits without the optional discovery snapshot stay **not recorded / unknown**; their evidence and scores are unchanged. Fresh demo audits include explicitly labelled fixture checks with zero HTTP requests. Comparisons can now resolve `robots_absent` or `sitemap_absent` only when the other audit retains a successful same-origin 2xx check of the corresponding kind, confirms presence, finishes deterministic analysis, uses matching rules and assesses the same nonempty URL set. A state label or omitted finding alone cannot prove resolution. Rules version 2 and score version 1 remain unchanged.

## Explain the health score

Open **Coverage matters → How is the score calculated?** to inspect the saved score calculation. New audits record the raw rule points and capped penalty for each assessed page, the mean page penalty, site-rule points and their combined 20-point cap, the unrounded score, and page records excluded from the denominator. Expand a page to inspect its contributing rules; **Search this URL in findings** opens the Issues tab with the URL search applied. That search also matches descendants and grouped affected URLs.

Critical/High/Medium/Low weights remain 20/10/5/2. Each rule counts once per affected page, page penalties cap at 100, and HTTP-error pages receive 100 regardless of their rule totals. The final score rounds to the nearest integer with ties to even, then clamps to 0–100. The dashboard displays intermediate numbers to at most four decimal places; saved JSON retains full numeric precision. No assessed pages means no score, and unknown/excluded pages do not improve the denominator. Exclusion details cover retained page records, while discovered but unfetched URLs remain in coverage counts.

Markdown, CSV and JSON reports include the same calculation snapshot. CSV separates `score_breakdown`, `page_penalty`, `page_score_rule`, `site_score_rule` and `excluded_score_page` records. Existing scores without a breakdown remain explicitly **not recorded** and are never recalculated. Recommendation approvals and intentional/dismissed findings do not remove recorded deductions. A fresh audit is required to assess changes; this diagnostic arithmetic does not forecast rankings, traffic or gains from a proposed fix. The feature makes no extra crawl or AI requests and preserves rule/score versions.

## Checks

Backend checks, from the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
.\.venv\Scripts\python.exe -m ruff check backend scripts
.\.venv\Scripts\python.exe scripts/check_repository.py --history
npm --prefix repository-tools test
npm --prefix validation ci --ignore-scripts
npm --prefix validation test
```

pytest deliberately ignores local dotenv files and masks inherited API keys. It uses offline fixtures and harmless SDK fakes. Live paid testing is separate and requires explicit authorization; configuring `backend/.env` does not make routine tests billable. The AI client uses the verified system certificate store, with hostname validation enabled, just like the crawler. For connection errors, check the network and trusted OS certificate configuration; never disable TLS verification.

Frontend checks, from `frontend/`:

```powershell
npm run lint
npm run typecheck
npm run test:proxy
npm run build
```

The committed lockfiles record tested dependencies. For a fully constrained Python install, add `-c backend/requirements.lock` to the installation command. A production dashboard starts with `npm run start` after building, alongside the same API service. Stop the existing dashboard process before rebuilding, then start it again: a running production process can retain asset paths from the previous build. From the repository root, use `npm --prefix frontend run build`, then `npm --prefix frontend run start` after the old process has stopped.

Run the repository check before commits and pushes. It checks working files, staged bytes, reachable history, ignored private paths and obvious credential patterns without printing potential secret values. GitHub Actions repeats the offline checks on pushes and pull requests, including contract drift, proxy tests, lint/type checks and a production build. No live key is supplied to CI. The [first hosted run passed](https://github.com/thanushreesuresh/SEOpilot/actions/runs/40120505329) for implementation commit `3a90c3c`.

Regenerate shared API types after contract changes:

```powershell
.\.venv\Scripts\python.exe scripts/export_openapi.py
cd frontend
npm run generate:types
```

Browser scenarios are in `frontend/e2e/`. GitHub Actions installs Chromium and runs `npm run test:e2e` with disabled live credentials and a disposable database. All **26 desktop/mobile, keyboard and error-state scenarios passed** on source `da67735` in the [current hosted run](https://github.com/thanushreesuresh/SEOpilot/actions/runs/40135903810), including reporting/JSON-LD, cancellation/retry/history, retained evidence and keyboard table scrolling. The hosted mobile screenshot was inspected. Earlier baselines remain recorded separately in the [verification record](docs/verification.md).

For a separately authorized browser environment, install Chromium with `npx --no-install playwright install chromium`, then run `npm run test:e2e` from `frontend/`. These commands start local services when needed. They were not used to obtain a local browser acceptance pass in this session.

## Three-minute demonstration

1. Start both services and open [the local dashboard](http://localhost:3000).
2. Select **Explore sample audit**. Confirm the visible sample disclosure and fixture revision; its bundled HTML includes a simulated missing page and curated optimization suggestions. Open the score explanation and robots/sitemap checks to inspect the saved evidence.
3. Filter **High** findings. Open the internal-link finding, inspect its URL/status evidence, then approve or reject its recommendation. Copy a suggestion; no website is changed.
4. Open **Recommendations** and inspect the labelled sample title/description suggestions. Download a Markdown, CSV, or JSON report. Open **Pages** for the JSON-LD summaries, then **Audit history**, reopen the audit, and confirm the saved decision. If two compatible saved audits are available, use **Compare audits**; repeated sample requests reuse the current revision and do not create a comparison pair.
5. For a real audit, enter `https://example.com/`, set link depth to **Starting page only**, and run the audit. Results and the score come from current fetched HTML. The AI panel reports unavailable until configured.

The server owns the fixture revision. After an upgrade with changed fixtures, **Explore sample audit** creates one new current sample and preserves old sample results, scores and decisions. Repeated/concurrent requests reuse that revision, including after restart and when it falls outside the latest 100 history rows. Reopening an old sample keeps its old evidence and labels an unrecorded revision as historical; it never silently reanalyzes that record. Reports include the recorded fixture revision. Samples set `allow_ai=false`, make no website/provider requests and consume no live-audit allowance, including when that allowance is exhausted. The existing 10-request/minute burst guard still applies to sample-opening requests.

For a bounded real API smoke test while the backend is running:

```powershell
.\.venv\Scripts\python.exe scripts/smoke_audit.py
```

The smoke test sends `allow_ai=false`, even if the running API has live AI configured. It consumes one live audit admission unless a matching audit is reused.

## Status

The genuine legacy-upgrade checkpoint, source [`6231133`](https://github.com/thanushreesuresh/SEOpilot/commit/6231133bbb465f3fba2b0f7c2b69601c07df09d9), passed [all hosted checks](https://github.com/thanushreesuresh/SEOpilot/actions/runs/40145002773): **598 backend tests and 46 browser scenarios**, plus AST/validator/proxy tests, lint/type/build, generated-contract drift and credential/history checks. Upgraded recent normal-audit requests now reuse their original admission format; genuine historical fixtures verify decisions, scores and counters survive. The [release-readiness report](docs/release-readiness.md) records the supported portfolio home page and remaining App/workflow/build/deployment gates. App setup was pending at that checkpoint; the later live connection check is recorded below. Manual local restart and human review remain pending.

The optional GitHub setup isolation checkpoint, source [`dca6465`](https://github.com/thanushreesuresh/SEOpilot/commit/dca6465843d8565429fa39e6d2a8e036aa33cb83), passed [all hosted checks](https://github.com/thanushreesuresh/SEOpilot/actions/runs/40143543032): **583 backend tests and 46 browser scenarios**, plus AST/validator/proxy tests, lint/type/build, generated-contract drift and credential/history checks. Invalid optional App settings now disable repository access while preserving audit startup, queued work, history and decisions. Safe error guidance, desktop audit access and mobile keyboard recovery passed; the mobile screenshot was inspected. Corrected settings require manual backend restart. Real App/pilot/deployment acceptance and human review remain pending.

The private connection diagnostics checkpoint, source [`3815886`](https://github.com/thanushreesuresh/SEOpilot/commit/38158868473a40883d85ad84d1e43362cefe8a40), passed [all hosted checks](https://github.com/thanushreesuresh/SEOpilot/actions/runs/40142551431): **571 backend tests and 44 browser scenarios**, plus AST/validator/proxy tests, lint/type/build, generated-contract drift and credential/history checks. The dashboard now distinguishes verified repository access from local setting presence, gives fixed safe guidance and clears stale onboarding access during refresh. Error states, legacy responses and mobile keyboard recovery passed; the mobile screenshot was inspected. Real App configuration, manual service restart, owner workflow, pilot approval/deployment and human review remain pending.

The revision-aware sample checkpoint, source [`1482a5c`](https://github.com/thanushreesuresh/SEOpilot/commit/1482a5ca227acf9e3260fc3708b3a2d2d1a76ce2), passed [all hosted checks](https://github.com/thanushreesuresh/SEOpilot/actions/runs/40141578038): **549 backend tests and 36 browser scenarios**, plus AST/validator/proxy tests, lint/type/build, generated-contract drift and credential/history checks. Opening the sample now reuses the current fixture revision while preserving historical samples, decisions and allowances. Mobile keyboard failure/retry checks passed and the screenshot was inspected. The [GitHub App guide](docs/github-app-setup.md) now includes exact fields and local configuration for the owned portfolio pilot. Manual service restart, App setup, owner workflow, pilot approval/deployment and human review remain pending.

The explainable-score checkpoint, source [`11f46b4`](https://github.com/thanushreesuresh/SEOpilot/commit/11f46b401b6ec84df8422bec8545890c737363c5), passed [all hosted checks](https://github.com/thanushreesuresh/SEOpilot/actions/runs/40139477667): **534 backend tests and 33 browser scenarios**, plus AST/validator/proxy tests, lint/type/build, generated-contract drift and credential/history checks. New audits retain score deductions and exclusions; desktop/mobile navigation, escaping, legacy/no-score states and computed readability checks passed. Historical scores and usage counters are unchanged. Local services still need manual restart; owned-pilot approval/deployment and human review remain pending.

The crawl-discovery checkpoint, source [`78dd569`](https://github.com/thanushreesuresh/SEOpilot/commit/78dd569fb0a45b7afe7082b68afb8bece43500be), passed [all hosted checks](https://github.com/thanushreesuresh/SEOpilot/actions/runs/40137186217): **521 backend tests and 29 browser scenarios**, plus AST/validator/proxy tests, lint/type/build, generated-contract drift and credential/history checks. Desktop and mobile evidence screenshots were inspected. This adds retained robots/sitemap probes and evidence-backed site-policy comparisons without additional requests or AI calls. Existing local services still require manual restart; GitHub App pilot setup and human release acceptance remain pending.

V2 implements project onboarding, source mapping, private patch review/download, explicit hash-bound draft-PR publication, recovery after uncertain writes, hosted validation reports, finding dispositions and fix-run history. It never merges or deploys changes. **PR opened**, **checks passed**, **merged**, **awaiting deployment** and **live verified** are separate states.

The saved-evidence milestone adds audit comparisons, Markdown/CSV/JSON evidence reports, and bounded JSON-LD diagnostics. [Its hosted checks passed](https://github.com/thanushreesuresh/SEOpilot/actions/runs/40132659834) all **465 backend tests and 23 browser scenarios**, plus AST/validator/proxy tests, linting, type checks, contract drift and production build. The mobile history-header overflow was fixed and keyboard table scrolling verified. All three report formats were also verified through the local API while preserving existing counters. This earlier pass does not cover the cancellation milestone described above.

Only TypeScript App Router server-page titles and descriptions are edited. The pinned AST parser in `repository-tools/` never executes target imports, configuration or scripts. Dynamic metadata, Client Components, ambiguous routes, percent-encoded route paths and uncertain inheritance/title templates require manual work. Shared layouts, canonicals, indexing directives, page content, dependencies and workflows are never automatically edited. Proposals are limited to three pages, five files and 100 changed lines; patch generation makes zero additional AI calls and private source stays outside OpenAI requests.

Publication allows two draft PRs globally per rolling 24 hours and one active fix per project. Each branch is `seopilot/<fix-run-id>` with one approved commit; stale or conflicting edits are rejected. GitHub status checks pause after ten minutes and can resume through **Refresh status**. Source and patches expire after 24 hours; active-server cleanup purges them, expired exports fail closed, and immediate deletion/disconnection controls are available. GitHub Actions usage is separate from the OpenAI allowance.

After manually merging and deploying, choose **Verify live**. It starts a fresh bounded audit of the recorded URLs with AI disabled and the existing three-audits/IP allowance. Missing, blocked, failed, interrupted, cancelled or truncated metadata cannot pass. A cancelled verification fails visibly; retrying creates a new audit and admission. Historical scores and rule/scoring versions are retained; reduced coverage is never reported as improvement. Deployment reports now reuse the same conservative field/coverage/formula comparison as saved audits and expose unresolved observations separately. Dispositions record reasons without rewriting evidence or scores.

The **prior V2 baseline** was verified locally and on GitHub with 356 backend tests, 34 AST tests, seven validator tests, seven proxy tests, Ruff, ESLint, TypeScript, a production build, and 15 hosted browser scenarios. These results precede the comparison/report/JSON-LD changes and are not acceptance evidence for this iteration. See [verification](docs/verification.md). A copied-database migration and the local runtime upgrade preserved existing audit, decision and usage records; counters were never reset. Earlier real SEO/AI observations remain in the [live record](docs/live-validation-2026-10-25.md).

The [release-readiness audit](docs/release-readiness.md) maps the v2 requirements to source/tests and records a pinned public-source check of the owned pilot. Its home page supports a page-level metadata override; dynamic project routes remain manual. The owner workflow is absent at the inspected commit; the declared lint script has no observed ESLint configuration and needs owner review before CI.

The selected owned pilot is [thanushree-portfolio](https://github.com/thanushreesuresh/thanushree-portfolio) at [thanushree-portfolio-six.vercel.app](https://thanushree-portfolio-six.vercel.app/). At 2026-10-25T06:23:12+05:30, the installed App's real authentication, scoped repository access, isolated API mapping and local home-page metadata probe passed; all 116 targeted App/workflow tests passed. The running backend still needs manual restart to load the configured settings. The owner validation workflow is missing. Saved project mapping, reviewed wording/diff, an explicitly approved pilot draft PR, hosted checks, manual merge/deployment and live verification remain pending. No OpenAI calls, repository writes or original counter changes occurred during these tests. See [connection evidence](docs/verification.md#installed-app-live-connection-check); human review remains pending.

The app remains local/single-user. The crawler parses fetched HTML without JavaScript and stays on the exact submitted origin. Search Console, public hosting/authentication, additional frameworks, local/ZIP imports, recurring audits, orphan detection and automatic merging/deployment are deferred. Full details: [architecture and scoring](docs/architecture.md), [verification](docs/verification.md), and [submission record](SUBMISSION.md).

## Sources and project record

Purposeful libraries: [Next.js](https://nextjs.org/), [Tailwind CSS](https://tailwindcss.com/), [FastAPI](https://fastapi.tiangolo.com/), [Pydantic](https://docs.pydantic.dev/), [HTTPcore](https://www.encode.io/httpcore/), [Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/bs4/doc/), [Protego](https://github.com/scrapy/protego), [OpenAI Python SDK](https://github.com/openai/openai-python), [pytest](https://docs.pytest.org/), and [Ruff](https://docs.astral.sh/ruff/). SQLite uses Python's standard library. No external SEO dataset is used.

Next.js/React/Tailwind and Lucide provide the interface; FastAPI/Uvicorn/Pydantic provide the typed local API; HTTPcore exposes the public transport hook needed for DNS pinning; Beautiful Soup and Protego handle HTML and robots parsing; the OpenAI SDK supplies optional structured output; python-dotenv loads local server configuration. HTTPX calls GitHub with verified TLS; [PyJWT](https://pyjwt.readthedocs.io/) and [cryptography](https://cryptography.io/) sign App JWTs. The [TypeScript compiler API](https://github.com/microsoft/TypeScript/wiki/Using-the-Compiler-API) parses source without executing it. OpenAPI TypeScript prevents contract drift. pytest/pytest-asyncio, Ruff, ESLint and Playwright support validation. No agent framework or external database service is required.

Important implementation areas are `backend/seopilot/network.py` and `crawler.py` (network/crawl policy), `extraction.py` and `rules.py` (page evidence and findings), `ai.py` (structured analysis/review), `storage.py`/`runner.py`/`app.py` (persistence and orchestration), and `frontend/src/components/` (dashboard). Generated frontend types are in `frontend/src/lib/api-types.ts`.

This repository began with the DevDay Exchange Kochi documentation template. Original [event rules](RULES.md) and [agent guidance](AGENTS.md) are preserved. Current development uses actual timestamps and makes no claim about event eligibility or organizer submission. See [CHANGELOG.md](CHANGELOG.md), [AI_USAGE.md](AI_USAGE.md), and [SUBMISSION.md](SUBMISSION.md).
