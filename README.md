# SEOPilot

Evidence-based SEO audits and reviewed metadata fixes for websites you own. Audit a public website, review findings, prepare a precise Next.js title/description patch, then explicitly approve a draft GitHub PR. GitHub-hosted checks and a separate live audit verify the change after you merge and deploy. Optional OpenAI analysis adds contextual suggestions; deterministic audits and patch generation work without paid services.

## Local setup (Windows PowerShell)

Requires Node.js 22+ and Python 3.13+. Run from the repository root:

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

The safe API entry point binds loopback, disables forwarded-header trust and access logs, and starts one worker. If invoking Uvicorn directly, include **`--no-proxy-headers --no-access-log`** and keep `--host 127.0.0.1`. Do not run multiple workers.

## Audit and spending protection

- Three accepted live audits per IP per **rolling 24 hours**. A fourth distinct audit receives `429` and `Retry-After` until the oldest admission expires. Counters persist across restarts and concurrent submissions. Admitted failures still count; invalid URLs and a full queue do not.
- Identical requests from the same IP reuse an active audit, or a completed result admitted within 15 minutes, without consuming another admission or triggering another AI stage. Context, crawl options and the AI opt-out are part of the match.
- At most two paid requests per audit: generation and review. Each must reserve a global allowance before calling OpenAI. Errors/timeouts retain their reservation, SDK retries are disabled, and unreviewed suggestions never publish. Output and UTF-8 input sizes are bounded. Reaching the cap preserves deterministic results.
- `GET /api/usage` exposes allowance/reset information; `allow_ai=false` opts an audit out of paid calls. The labelled sample uses no live quota or paid calls and repeated sample requests reuse its result. The real smoke-test command explicitly opts out of AI.
- The dashboard displays your remaining audits and next reset, the shared AI-call allowance, a no-AI option and duplicate-reuse notices. You can refresh the allowance after a reset; sample mode remains available when live quota is exhausted.
- The Next server derives client identity from its socket and authenticates it to the fixed loopback backend using a private generated token. Incoming forwarding/IP/token headers are discarded. The backend stores HMAC identities, groups IPv6 addresses by `/64`, and accepts stamped identity only from an authenticated loopback proxy.

Local browsers normally share one loopback allowance. A reverse proxy in front of Next also shares one conservative bucket; arbitrary forwarding headers are never trusted. Preserve the SQLite database and its quota salt when restarting: deleting/replacing it resets local counters. The proxy token is generated in ignored `backend/.data/proxy-token` and stays outside production bundles.

This release remains **local and single-user**. IP limits cannot stop a botnet by themselves; the global AI cap provides the additional spending boundary. Before public hosting, add authentication, audit ownership checks and a trusted edge with rate limits. For a monetary ceiling, also configure a dedicated OpenAI project with a restricted key and [project spend limits](https://developers.openai.com/api/docs/guides/spend-limits); application request counts are not billing telemetry. Provider spend-limit enforcement may have a short delay. Live `gpt-6-luna` access and a complete generation/review workflow have been tested; see the [bounded live verification record](docs/live-validation-2026-10-25.md).

No credentials are required for the labelled sample demo. Recommendation approval records content review. A separate **Create draft PR** action authorizes the exact inspected patch; merge and deployment remain manual.

Optional AI now uses structured generation followed by a separate evidence review. Invalid, unsupported or contradictory suggestions are withheld. Missing credentials, rate limits, timeouts and provider errors preserve deterministic findings. The sample audit parses bundled HTML through the production extractor and rules and clearly identifies curated suggestions as sample data.

## Architecture

Next.js proxies allowlisted `/api/*` routes to FastAPI. One lifespan-managed asynchronous worker processes persisted audit and fix stages. Crawling, extraction, deterministic rules, AI analysis/review, GitHub access, static AST patching and storage remain separate modules. Pydantic defines the API contracts; frontend types are generated from OpenAPI. SQLite schema v3 preserves existing audits and counters while adding project connections, immutable proposals, execution events, publication reservations and finding dispositions.

Indexing evidence retains up to ten combined robots meta/header directives. Additional directives mark that field incomplete, so live verification cannot accept a matching prefix as the complete indexing policy.

Queued jobs survive restarts. Active jobs become interrupted, retain collected evidence, and can be rerun as a new audit. Network requests never hold database transactions. Audit history is local data and is ignored by Git.

## Saved comparisons, reports, and JSON-LD checks

Open **Audit history → Compare audits**, select **Earlier audit** and **Later audit**, then choose **Run comparison**. The selector uses the latest 100 saved audits. Both audits must be finished (`completed`, `partial`, `failed`, or `interrupted`), use the same mode (live or sample), and have the same normalized origin, including scheme, hostname, and port. They must be different audits, and the baseline must have an earlier creation time. Comparing saved results starts no crawl, consumes no live-audit admission, and makes no AI calls.

Finding changes use rule ID, normalized URL, primary evidence field, and site/page scope rather than random finding IDs. The view separates added, persistent, resolved, and unresolved/unknown findings; filters by change status or URL; and shows shared, newly assessed, and removed URLs. Missing follow-up pages, blocked or unchecked evidence, truncated fields, unfinished analysis, or different rules cannot establish a fix. Newly assessed coverage is not reported as a regression. A score delta appears only when both audits have equal complete, untruncated coverage, matching rule/score versions and score formulas, available scores, and no unresolved/unknown findings. Historical scores stay unchanged; these comparisons do not measure rankings or traffic.

In an audit overview, choose **Report format → Markdown, CSV, or JSON → Download report**. Reports use saved findings and evidence, score/formula/version information, coverage, recommendations and their review status, decision/disposition history, and limitations. AI and sample suggestions retain their hypothesis and human-review labels. Reports are available after the audit finishes and make no new crawl or AI calls. Report content and its JSON response envelope are each bounded to **1 MiB**; oversized exports return an error rather than a clipped report. CSV uses standard quoting and prefixes formula-like cells, including whitespace-hidden prefixes, with an apostrophe. Markdown escapes source text. Exports exclude credentials and private repository source.

| Endpoint | Saved-data operation |
| --- | --- |
| `POST /api/audit-comparisons` | JSON body: `{"before_audit_id":"<earlier UUID>","after_audit_id":"<later UUID>"}`; returns finding changes, coverage, versions, and a nullable score delta |
| `GET /api/audits/{audit_id}/report/{format}` | `format` is `markdown`, `csv`, or `json`; returns `filename`, `media_type`, and `content` for download |

Open the **Pages** tab to inspect each page's JSON-LD summary. New HTML extraction retains declared type labels and bounded syntax/context observations; raw JSON-LD scripts are discarded. Inspection covers at most 10 blocks, 16 KiB per block, 64 KiB combined, nesting depth 32, 20 distinct type labels, and 50 observations. Limits and clipped HTML leave evidence incomplete; older saved pages without this inspection remain unknown. The checker does not fetch contexts, execute scripts, validate all Schema.org requirements, or establish rich-result eligibility. Missing or unfamiliar contexts receive review advice because custom vocabularies and fully qualified IRIs can be intentional.

New deterministic analyses record **rules version 2** for the JSON-LD diagnostics. Existing saved audits keep rules version 1 and their original findings and scores; score version remains **1**. A fresh audit is needed to collect the new evidence. Comparisons disclose version differences and withhold conclusions that the retained evidence cannot support.

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

The committed lockfiles record tested dependencies. For a fully constrained Python install, add `-c backend/requirements.lock` to the installation command. A production dashboard starts with `npm run start` after building, alongside the same API service.

Run the repository check before commits and pushes. It checks working files, staged bytes, reachable history, ignored private paths and obvious credential patterns without printing potential secret values. GitHub Actions repeats the offline checks on pushes and pull requests, including contract drift, proxy tests, lint/type checks and a production build. No live key is supplied to CI. The [first hosted run passed](https://github.com/thanushreesuresh/SEOpilot/actions/runs/40120505329) for implementation commit `3a90c3c`.

Regenerate shared API types after contract changes:

```powershell
.\.venv\Scripts\python.exe scripts/export_openapi.py
cd frontend
npm run generate:types
```

Browser scenarios are in `frontend/e2e/`. GitHub Actions installs Chromium and runs `npm run test:e2e` with disabled live credentials and a disposable database. The **prior V2 baseline of 15 desktop/mobile, keyboard and error-state scenarios passed** in the [hosted run](https://github.com/thanushreesuresh/SEOpilot/actions/runs/40128792918); its mobile review screenshot was inspected. The current suite contains **23 scenarios**, including eight new reporting/JSON-LD cases, and awaits hosted execution. The prior pass does not verify this iteration. See the [verification record](docs/verification.md).

For a separately authorized browser environment, install Chromium with `npx --no-install playwright install chromium`, then run `npm run test:e2e` from `frontend/`. These commands start local services when needed. They were not used to obtain a local browser acceptance pass in this session.

## Three-minute demonstration

1. Start both services and open [the local dashboard](http://localhost:3000).
2. Select **Explore sample audit**. Confirm the visible sample disclosure; its bundled HTML includes a simulated missing page and curated optimization suggestions.
3. Filter **High** findings. Open the internal-link finding, inspect its URL/status evidence, then approve or reject its recommendation. Copy a suggestion; no website is changed.
4. Open **Recommendations** and inspect the labelled sample title/description suggestions. Download a Markdown, CSV, or JSON report. Open **Pages** for the JSON-LD summaries, then **Audit history**, reopen the audit, and confirm the saved decision. If two compatible saved audits are available, use **Compare audits**; repeated sample requests reuse one audit and do not create a comparison pair.
5. For a real audit, enter `https://example.com/`, set link depth to **Starting page only**, and run the audit. Results and the score come from current fetched HTML. The AI panel reports unavailable until configured.

For a bounded real API smoke test while the backend is running:

```powershell
.\.venv\Scripts\python.exe scripts/smoke_audit.py
```

The smoke test sends `allow_ai=false`, even if the running API has live AI configured. It consumes one live audit admission unless a matching audit is reused.

## Status

V2 implements project onboarding, source mapping, private patch review/download, explicit hash-bound draft-PR publication, recovery after uncertain writes, hosted validation reports, finding dispositions and fix-run history. It never merges or deploys changes. **PR opened**, **checks passed**, **merged**, **awaiting deployment** and **live verified** are separate states.

This iteration adds saved audit comparisons, Markdown/CSV/JSON evidence reports, and bounded JSON-LD diagnostics. Hosted checks pass 465 backend tests and 22 of 23 browser cases; mobile comparison overflow remains under investigation after containment alone failed. All three report formats were verified through the local API while preserving existing counters. The dashboard process needs restarting after the latest build. Full browser acceptance remains pending.

Only TypeScript App Router server-page titles and descriptions are edited. The pinned AST parser in `repository-tools/` never executes target imports, configuration or scripts. Dynamic metadata, Client Components, ambiguous routes, percent-encoded route paths and uncertain inheritance/title templates require manual work. Shared layouts, canonicals, indexing directives, page content, dependencies and workflows are never automatically edited. Proposals are limited to three pages, five files and 100 changed lines; patch generation makes zero additional AI calls and private source stays outside OpenAI requests.

Publication allows two draft PRs globally per rolling 24 hours and one active fix per project. Each branch is `seopilot/<fix-run-id>` with one approved commit; stale or conflicting edits are rejected. GitHub status checks pause after ten minutes and can resume through **Refresh status**. Source and patches expire after 24 hours; active-server cleanup purges them, expired exports fail closed, and immediate deletion/disconnection controls are available. GitHub Actions usage is separate from the OpenAI allowance.

After manually merging and deploying, choose **Verify live**. It starts a fresh bounded audit of the recorded URLs with AI disabled and the existing three-audits/IP allowance. Missing, blocked, failed or truncated metadata cannot pass. Historical scores and rule/scoring versions are retained; reduced coverage is never reported as improvement. Dispositions record reasons without rewriting evidence or scores.

The **prior V2 baseline** was verified locally and on GitHub with 356 backend tests, 34 AST tests, seven validator tests, seven proxy tests, Ruff, ESLint, TypeScript, a production build, and 15 hosted browser scenarios. These results precede the comparison/report/JSON-LD changes and are not acceptance evidence for this iteration. See [verification](docs/verification.md). A copied-database migration and the local runtime upgrade preserved existing audit, decision and usage records; counters were never reset. Earlier real SEO/AI observations remain in the [live record](docs/live-validation-2026-10-25.md).

The selected owned pilot is [thanushree-portfolio](https://github.com/thanushreesuresh/thanushree-portfolio) at [thanushree-portfolio-six.vercel.app](https://thanushree-portfolio-six.vercel.app/). The three local GitHub App settings are not configured. Release acceptance still requires the App installation, owner-installed workflow, an inspected pilot draft PR, manual merge/deployment and successful live verification. No pilot deployment or end-to-end release acceptance is claimed; human review remains pending.

The app remains local/single-user. The crawler parses fetched HTML without JavaScript and stays on the exact submitted origin. Search Console, public hosting/authentication, additional frameworks, local/ZIP imports, recurring audits, orphan detection and automatic merging/deployment are deferred. Full details: [architecture and scoring](docs/architecture.md), [verification](docs/verification.md), and [submission record](SUBMISSION.md).

## Sources and project record

Purposeful libraries: [Next.js](https://nextjs.org/), [Tailwind CSS](https://tailwindcss.com/), [FastAPI](https://fastapi.tiangolo.com/), [Pydantic](https://docs.pydantic.dev/), [HTTPcore](https://www.encode.io/httpcore/), [Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/bs4/doc/), [Protego](https://github.com/scrapy/protego), [OpenAI Python SDK](https://github.com/openai/openai-python), [pytest](https://docs.pytest.org/), and [Ruff](https://docs.astral.sh/ruff/). SQLite uses Python's standard library. No external SEO dataset is used.

Next.js/React/Tailwind and Lucide provide the interface; FastAPI/Uvicorn/Pydantic provide the typed local API; HTTPcore exposes the public transport hook needed for DNS pinning; Beautiful Soup and Protego handle HTML and robots parsing; the OpenAI SDK supplies optional structured output; python-dotenv loads local server configuration. HTTPX calls GitHub with verified TLS; [PyJWT](https://pyjwt.readthedocs.io/) and [cryptography](https://cryptography.io/) sign App JWTs. The [TypeScript compiler API](https://github.com/microsoft/TypeScript/wiki/Using-the-Compiler-API) parses source without executing it. OpenAPI TypeScript prevents contract drift. pytest/pytest-asyncio, Ruff, ESLint and Playwright support validation. No agent framework or external database service is required.

Important implementation areas are `backend/seopilot/network.py` and `crawler.py` (network/crawl policy), `extraction.py` and `rules.py` (page evidence and findings), `ai.py` (structured analysis/review), `storage.py`/`runner.py`/`app.py` (persistence and orchestration), and `frontend/src/components/` (dashboard). Generated frontend types are in `frontend/src/lib/api-types.ts`.

This repository began with the DevDay Exchange Kochi documentation template. Original [event rules](RULES.md) and [agent guidance](AGENTS.md) are preserved. Current development uses actual timestamps and makes no claim about event eligibility or organizer submission. See [CHANGELOG.md](CHANGELOG.md), [AI_USAGE.md](AI_USAGE.md), and [SUBMISSION.md](SUBMISSION.md).
