# SEOPilot

Evidence-based SEO audits for small businesses. Enter a public website URL, inspect actual page findings, and review practical recommendations. Optional OpenAI analysis adds contextual suggestions; the crawler and rules work without paid services.

## Local setup (Windows PowerShell)

Requires Node.js 22+ and Python 3.13+. Run from the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e "backend[dev]"
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

No credentials are required for the labelled sample demo. The app never modifies or publishes to the audited website.

Optional AI now uses structured generation followed by a separate evidence review. Invalid, unsupported or contradictory suggestions are withheld. Missing credentials, rate limits, timeouts and provider errors preserve deterministic findings. The sample audit parses bundled HTML through the production extractor and rules and clearly identifies curated suggestions as sample data.

## Architecture

Next.js proxies `/api/*` to FastAPI. A lifespan-managed asynchronous worker claims jobs from SQLite. Crawling, extraction, deterministic rules, AI analysis/review, and storage are separate Python modules. Pydantic defines the API contracts; frontend types are generated from OpenAPI. SQLite stores projects, audit runs, page metadata, findings, recommendations, and append-only review decisions.

Queued jobs survive restarts. Active jobs become interrupted, retain collected evidence, and can be rerun as a new audit. Network requests never hold database transactions. Audit history is local data and is ignored by Git.

## Checks

Backend checks, from the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
.\.venv\Scripts\python.exe -m ruff check backend scripts
.\.venv\Scripts\python.exe scripts/check_repository.py --history
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

Browser scenarios are in `frontend/e2e/`. With browser access permitted, `npm run test:e2e` from `frontend/` uses Playwright and starts missing local services. These scenarios were **not executed here** because the browser origin policy denied localhost, including after explicit approval and retry. See the [verification record](docs/verification.md).

## Three-minute demonstration

1. Start both services and open [the local dashboard](http://localhost:3000).
2. Select **Explore sample audit**. Confirm the visible sample disclosure; its bundled HTML includes a simulated missing page and curated optimization suggestions.
3. Filter **High** findings. Open the internal-link finding, inspect its URL/status evidence, then approve or reject its recommendation. Copy a suggestion; no website is changed.
4. Open **Recommendations** and inspect the labelled sample title/description suggestions. Open **Audit history**, reopen the audit, and confirm the saved decision.
5. For a real audit, enter `https://example.com/`, set link depth to **Starting page only**, and run the audit. Results and the score come from current fetched HTML. The AI panel reports unavailable until configured.

For a bounded real API smoke test while the backend is running:

```powershell
.\.venv\Scripts\python.exe scripts/smoke_audit.py
```

The smoke test sends `allow_ai=false`, even if the running API has live AI configured. It consumes one live audit admission unless a matching audit is reused.

## Status

The static metadata adapter is available in `repository-tools/`. Install its pinned parser with `cd repository-tools; npm ci` and run `npm test` there. It edits only TypeScript App Router server-page titles/descriptions and refuses dynamic metadata, Client Components, uncertain inheritance, unsupported title templates and ambiguous routes. It parses source without executing target imports, configuration or scripts. Patch review and publication are separate steps in the v2 dashboard integration.

V2 development adds a private GitHub App boundary, selected-repository authorization and versioned project/fix persistence while retaining audit and AI quotas. See [App setup](docs/github-app-setup.md). The draft-PR workflow is being integrated; no pilot PR or deployed change is claimed at this checkpoint.

The connected dashboard is implemented and its production build, TypeScript and ESLint checks pass. Rendered browser/E2E verification is blocked by the local browser origin permission policy; no browser or visual-fidelity pass is claimed. No deployment is claimed.

The real crawler and API are implemented and verified against a one-page example.com audit. Crawl limits, policy failures and extraction truncation remain visible as coverage information. The server uses validated-IP connections with normal TLS hostname verification and never follows links outside the submitted origin.

The deterministic rules now evaluate extracted metadata, heading structure, image alt presence, canonicals, indexing directives, confirmed internal-link failures, HTTP errors, duplicate titles/descriptions, and evidence-backed site discovery observations. Character ranges are configurable review heuristics, not ranking rules. The internal health score subtracts mean capped page penalties (Critical 20, High 10, Medium 5, Low 2; HTTP errors 100) and site penalties capped at 20. Unknown pages do not enter its denominator; insufficient data produces no score.

Verified: 207 backend tests and Ruff; prior frontend ESLint/TypeScript/build, six proxy tests and browser-bundle canary checks passed. Live Python.org sampling assessed three pages, verified eight observations and produced three evidence-reviewed AI suggestions; independent HTML checks and score arithmetic matched. Example.com scored 82; a TLS trust failure was reproduced and corrected, and a post-fix generation succeeded while the exhausted per-audit review allowance withheld its suggestions. See [actual results and limits](docs/live-validation-2026-10-25.md). Browser rendering, mobile interaction and screenshot fidelity remain unverified because of the origin permission block.

This MVP parses fetched HTML without JavaScript execution, stays on the exact submitted origin, and is local/single-user. Search Console, authentication/hosting, orphan detection, recurring audits and automatic publishing are deferred. Full details: [architecture and scoring](docs/architecture.md), [verification](docs/verification.md), and [submission record](SUBMISSION.md).

## Sources and project record

Purposeful libraries: [Next.js](https://nextjs.org/), [Tailwind CSS](https://tailwindcss.com/), [FastAPI](https://fastapi.tiangolo.com/), [Pydantic](https://docs.pydantic.dev/), [HTTPcore](https://www.encode.io/httpcore/), [Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/bs4/doc/), [Protego](https://github.com/scrapy/protego), [OpenAI Python SDK](https://github.com/openai/openai-python), [pytest](https://docs.pytest.org/), and [Ruff](https://docs.astral.sh/ruff/). SQLite uses Python's standard library. No external SEO dataset is used.

Next.js/React/Tailwind and Lucide provide the interface; FastAPI/Uvicorn/Pydantic provide the typed local API; HTTPcore exposes the public transport hook needed for DNS pinning; Beautiful Soup and Protego handle HTML and robots parsing; the OpenAI SDK supplies optional structured output; python-dotenv loads local server configuration. OpenAPI TypeScript prevents contract drift. pytest/pytest-asyncio, HTTPX, Ruff, ESLint, TypeScript and Playwright support validation. No agent framework, external database service or native database package is required.

Important implementation areas are `backend/seopilot/network.py` and `crawler.py` (network/crawl policy), `extraction.py` and `rules.py` (page evidence and findings), `ai.py` (structured analysis/review), `storage.py`/`runner.py`/`app.py` (persistence and orchestration), and `frontend/src/components/` (dashboard). Generated frontend types are in `frontend/src/lib/api-types.ts`.

This repository began with the DevDay Exchange Kochi documentation template. Original [event rules](RULES.md) and [agent guidance](AGENTS.md) are preserved. Current development uses actual timestamps and makes no claim about event eligibility or organizer submission. See [CHANGELOG.md](CHANGELOG.md), [AI_USAGE.md](AI_USAGE.md), and [SUBMISSION.md](SUBMISSION.md).
