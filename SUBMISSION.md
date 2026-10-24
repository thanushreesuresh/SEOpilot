# SEOPilot delivery and demonstration

## Project

- **Project name:** SEOPilot.
- **Description:** A local SEO audit application for small businesses: secure website crawling, evidence-backed deterministic findings, contextual AI suggestions when configured, and human recommendation review.
- **Code repository:** https://github.com/thanushreesuresh/SEOpilot
- **Verified implementation commit:** [f66d76108a0f0fd3d11df2c2d0f9862f0be7f42d](https://github.com/thanushreesuresh/SEOpilot/commit/f66d76108a0f0fd3d11df2c2d0f9862f0be7f42d). This revision contains the completed implementation and verification record; this subsequent documentation commit records its identity. Organizer submission has not been performed.
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
.\.venv\Scripts\python.exe -m uvicorn seopilot.app:app --app-dir backend --host 127.0.0.1 --port 8000
```

Start Next.js from `frontend/` in another:

```powershell
npm run dev
```

Demonstrate a labelled sample, inspect evidence and severity filters, approve/reject a recommendation, copy a suggestion, reopen history, then perform a real bounded audit. Approval never publishes changes.

Optional server-side environment names: `OPENAI_API_KEY`, `OPENAI_MODEL`, `SEOPILOT_DB`. Secrets are not included in this repository.

**Validation:** 177 backend tests, Ruff, ESLint, TypeScript and production build passed; live example.com API audit completed. Browser/E2E and screenshot fidelity are unverified because local-origin policy denied access. Live AI awaits credentials. See [verification details](docs/verification.md), [architecture](docs/architecture.md), [README](README.md), [AI usage](AI_USAGE.md) and [change log](CHANGELOG.md).

**Deferred:** Search Console, public hosting/authentication, automatic publishing, recurring audits and reliable orphan detection. No traffic, ranking, search-volume or other unavailable measurements are fabricated. Sources and dependencies are linked in README.

## Honest delivery checklist

- [x] Project description, repository and local demonstration instructions provided.
- [x] Core implementation and actual validation documented.
- [x] Codex contributions recorded; human review pending.
- [x] Secrets and local database files excluded from source control.
- [ ] Rendered desktop/mobile browser verification completed.
- [ ] Live AI integration verified with user-supplied credentials.
- [ ] Participant details and event eligibility verified.
- [ ] Organizer submission performed through its announced method and timing.

The original [event rules](RULES.md) remain preserved. This file records technical delivery readiness, not organizer acceptance.
