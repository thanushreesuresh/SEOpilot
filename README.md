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
.\.venv\Scripts\python.exe -m uvicorn seopilot.app:app --app-dir backend --host 127.0.0.1 --port 8000
```

Start the dashboard in a second terminal:

```powershell
cd frontend
npm run dev
```

Open [SEOPilot](http://localhost:3000). Keep both services on loopback. Use one API worker; this release is a single-user, single-computer application.

## Configuration

The backend reads process environment variables and an optional ignored `backend/.env`. `backend/.env.example` lists names without secrets:

- `OPENAI_API_KEY` and `OPENAI_MODEL`: both required to enable live AI. Leave unset for deterministic auditing. Supply credentials through your local environment; never put them in frontend variables or commits.
- `SEOPILOT_DB`: optional SQLite path, default `backend/.data/seopilot.db`.

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
```

Frontend checks, from `frontend/`:

```powershell
npm run lint
npm run typecheck
npm run build
```

The committed lockfiles record tested dependencies. For a fully constrained Python install, add `-c backend/requirements.lock` to the installation command. A production dashboard starts with `npm run start` after building, alongside the same API service.

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

The smoke test does not supply AI credentials. If the running API has live AI configured, its normal optional AI stage can still run.

## Status

The connected dashboard is implemented and its production build, TypeScript and ESLint checks pass. Rendered browser/E2E verification is blocked by the local browser origin permission policy; no browser or visual-fidelity pass is claimed. No deployment is claimed.

The real crawler and API are implemented and verified against a one-page example.com audit. Crawl limits, policy failures and extraction truncation remain visible as coverage information. The server uses validated-IP connections with normal TLS hostname verification and never follows links outside the submitted origin.

The deterministic rules now evaluate extracted metadata, heading structure, image alt presence, canonicals, indexing directives, confirmed internal-link failures, HTTP errors, duplicate titles/descriptions, and evidence-backed site discovery observations. Character ranges are configurable review heuristics, not ranking rules. The internal health score subtracts mean capped page penalties (Critical 20, High 10, Medium 5, Low 2; HTTP errors 100) and site penalties capped at 20. Unknown pages do not enter its denominator; insufficient data produces no score.

Verified: 177 backend tests, Ruff, frontend ESLint, TypeScript, production build, and a real one-page API audit. Live AI is untested without credentials. Browser rendering, mobile interaction and screenshot fidelity remain unverified because of the origin permission block.

This MVP parses fetched HTML without JavaScript execution, stays on the exact submitted origin, and is local/single-user. Search Console, authentication/hosting, orphan detection, recurring audits and automatic publishing are deferred. Full details: [architecture and scoring](docs/architecture.md), [verification](docs/verification.md), and [submission record](SUBMISSION.md).

## Sources and project record

Purposeful libraries: [Next.js](https://nextjs.org/), [Tailwind CSS](https://tailwindcss.com/), [FastAPI](https://fastapi.tiangolo.com/), [Pydantic](https://docs.pydantic.dev/), [HTTPcore](https://www.encode.io/httpcore/), [Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/bs4/doc/), [Protego](https://github.com/scrapy/protego), [OpenAI Python SDK](https://github.com/openai/openai-python), [pytest](https://docs.pytest.org/), and [Ruff](https://docs.astral.sh/ruff/). SQLite uses Python's standard library. No external SEO dataset is used.

Next.js/React/Tailwind and Lucide provide the interface; FastAPI/Uvicorn/Pydantic provide the typed local API; HTTPcore exposes the public transport hook needed for DNS pinning; Beautiful Soup and Protego handle HTML and robots parsing; the OpenAI SDK supplies optional structured output; python-dotenv loads local server configuration. OpenAPI TypeScript prevents contract drift. pytest/pytest-asyncio, HTTPX, Ruff, ESLint, TypeScript and Playwright support validation. No agent framework, external database service or native database package is required.

Important implementation areas are `backend/seopilot/network.py` and `crawler.py` (network/crawl policy), `extraction.py` and `rules.py` (page evidence and findings), `ai.py` (structured analysis/review), `storage.py`/`runner.py`/`app.py` (persistence and orchestration), and `frontend/src/components/` (dashboard). Generated frontend types are in `frontend/src/lib/api-types.ts`.

This repository began with the DevDay Exchange Kochi documentation template. Original [event rules](RULES.md) and [agent guidance](AGENTS.md) are preserved. Current development uses actual timestamps and makes no claim about event eligibility or organizer submission. See [CHANGELOG.md](CHANGELOG.md), [AI_USAGE.md](AI_USAGE.md), and [SUBMISSION.md](SUBMISSION.md).
