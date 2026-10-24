# SEOPilot delivery and demonstration

## Project

- **Project name:** SEOPilot.
- **Description:** A local SEO audit application for small businesses: secure website crawling, evidence-backed deterministic findings, contextual AI suggestions when configured, and human recommendation review.
- **Code repository:** https://github.com/thanushreesuresh/SEOpilot
- **Original verified MVP commit:** [f66d76108a0f0fd3d11df2c2d0f9862f0be7f42d](https://github.com/thanushreesuresh/SEOpilot/commit/f66d76108a0f0fd3d11df2c2d0f9862f0be7f42d). Later security/configuration and allowance-interface changes are recorded in CHANGELOG; this earlier SHA does not include them. Organizer submission has not been performed.
- **Verified security/allowance implementation:** [3a90c3cd24662eb11bd6ea1067ea7a07a6c754f9](https://github.com/thanushreesuresh/SEOpilot/commit/3a90c3cd24662eb11bd6ea1067ea7a07a6c754f9), including [passing hosted checks](https://github.com/thanushreesuresh/SEOpilot/actions/runs/40120505329). This later documentation checkpoint records the result.
- **Working demo:** Follow the README's local setup and three-minute demonstration at http://localhost:3000.
- **Access requirements:** Node.js 22+, Python 3.13+, local loopback services. No credentials required for deterministic audits or labelled sample mode.

## Participants and event status

Participant names and event eligibility have not been supplied or verified. The repository owner is not automatically assumed to be the participant. Current implementation uses actual 24 October 2026 timestamps and does not claim development took place during the 10–11 October event.

## Run and demonstrate

Install from the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -c backend/requirements.lock -e "backend[dev]"
cd frontend
npm ci
```

Start FastAPI from the root in one terminal:

```powershell
.\.venv\Scripts\python.exe -m seopilot
```

Start Next.js from `frontend/` in another:

```powershell
npm run dev
```

Demonstrate a labelled sample, inspect evidence and severity filters, approve/reject a recommendation, copy a suggestion, reopen history, then perform a real bounded audit. Approval never publishes changes.

Use the blank `backend/.env.example` template and put your future key only in ignored `backend/.env`. Model: `gpt-6-luna`. The README lists the server kill switch, global call/output limits, database and private proxy-token configuration. Three accepted live audits per IP per rolling 24 hours, duplicate reuse and durable paid-call reservations protect local use. Samples and the smoke-test command make zero paid calls. Secrets are not included in this repository.

**Validation:** 207 backend tests and Ruff passed; prior six Node proxy tests, ESLint, TypeScript/build and secret-marker checks passed. Live Python.org generation/review produced three grounded AI suggestions; raw HTML observations and both sites' scores were independently checked. Example transport failed, then passed verified TLS/model/generation checks; its review was withheld when the lifetime allowance was exhausted. Browser/E2E and screenshot fidelity remain unverified under local-origin policy. See [live verification](docs/live-validation-2026-10-25.md), [verification details](docs/verification.md), [architecture](docs/architecture.md), [README](README.md), [AI usage](AI_USAGE.md) and [change log](CHANGELOG.md).

**Deferred:** Search Console, public hosting/authentication, automatic publishing, recurring audits and reliable orphan detection. No traffic, ranking, search-volume or other unavailable measurements are fabricated. Sources and dependencies are linked in README.

## Honest delivery checklist

- [x] Project description, repository and local demonstration instructions provided.
- [x] Core implementation and actual validation documented.
- [x] Codex contributions recorded; human review pending.
- [x] Secrets and local database files excluded from source control.
- [ ] Rendered desktop/mobile browser verification completed.
- [x] Live AI integration verified with user-supplied credentials; bounded results and limits recorded.
- [ ] Participant details and event eligibility verified.
- [ ] Organizer submission performed through its announced method and timing.

The original [event rules](RULES.md) remain preserved. This file records technical delivery readiness, not organizer acceptance.
