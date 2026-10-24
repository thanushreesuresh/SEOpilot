# SEOPilot

Evidence-based SEO audits for small businesses. Enter a public website URL, inspect actual page findings, and review practical recommendations. Optional OpenAI analysis adds contextual suggestions; the crawler and rules work without paid services.

## Local setup (Windows PowerShell)

Requires Node.js 22+ and Python 3.13+. Run from the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e "backend[dev]"
npm --prefix frontend install
```

Start the API in one terminal:

```powershell
.\.venv\Scripts\python.exe -m uvicorn seopilot.app:app --app-dir backend --host 127.0.0.1 --port 8000
```

Start the dashboard in a second terminal:

```powershell
npm --prefix frontend run dev
```

Open [SEOPilot](http://localhost:3000). Keep both services on loopback. Use one API worker; this release is a single-user, single-computer application.

## Configuration

The backend reads process environment variables and an optional ignored `backend/.env`. `backend/.env.example` lists names without secrets:

- `OPENAI_API_KEY` and `OPENAI_MODEL`: both required to enable live AI. Leave unset for deterministic auditing. Supply credentials through your local environment; never put them in frontend variables or commits.
- `SEOPILOT_DB`: optional SQLite path, default `backend/.data/seopilot.db`.

No credentials are required for the labelled sample demo. The app never modifies or publishes to the audited website.

## Architecture

Next.js proxies `/api/*` to FastAPI. A lifespan-managed asynchronous worker claims jobs from SQLite. Crawling, extraction, deterministic rules, AI analysis/review, and storage are separate Python modules. Pydantic defines the API contracts; frontend types are generated from OpenAPI. SQLite stores projects, audit runs, page metadata, findings, recommendations, and append-only review decisions.

Queued jobs survive restarts. Active jobs become interrupted, retain collected evidence, and can be rerun as a new audit. Network requests never hold database transactions. Audit history is local data and is ignored by Git.

## Checks

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
.\.venv\Scripts\python.exe -m ruff check backend scripts
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run build
```

Regenerate shared API types after contract changes:

```powershell
.\.venv\Scripts\python.exe scripts/export_openapi.py
npm --prefix frontend run generate:types
```

## Status

Implementation is in progress. Validation results and the full demo workflow are recorded in subsequent milestone documentation; no live AI or deployment is claimed.

The deterministic rules now evaluate extracted metadata, heading structure, image alt presence, canonicals, indexing directives, confirmed internal-link failures, HTTP errors, duplicate titles/descriptions, and evidence-backed site discovery observations. Character ranges are configurable review heuristics, not ranking rules. The internal health score subtracts mean capped page penalties (Critical 20, High 10, Medium 5, Low 2; HTTP errors 100) and site penalties capped at 20. Unknown pages do not enter its denominator; insufficient data produces no score.

## Sources and project record

Purposeful libraries: [Next.js](https://nextjs.org/), [Tailwind CSS](https://tailwindcss.com/), [FastAPI](https://fastapi.tiangolo.com/), [Pydantic](https://docs.pydantic.dev/), [HTTPcore](https://www.encode.io/httpcore/), [Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/bs4/doc/), [Protego](https://github.com/scrapy/protego), [OpenAI Python SDK](https://github.com/openai/openai-python), [pytest](https://docs.pytest.org/), and [Ruff](https://docs.astral.sh/ruff/). SQLite uses Python's standard library. No external SEO dataset is used.

This repository began with the DevDay Exchange Kochi documentation template. Original [event rules](RULES.md) and [agent guidance](AGENTS.md) are preserved. Current development uses actual timestamps and makes no claim about event eligibility or organizer submission. See [CHANGELOG.md](CHANGELOG.md), [AI_USAGE.md](AI_USAGE.md), and [SUBMISSION.md](SUBMISSION.md).
