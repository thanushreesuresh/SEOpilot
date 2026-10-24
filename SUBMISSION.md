# SEOPilot delivery and demonstration

## Project

- **Project name:** SEOPilot.
- **Description:** Local evidence-based SEO auditing with optional reviewed AI suggestions and a GitHub App workflow for inspected Next.js metadata patches, draft PRs, hosted validation and explicit post-deployment verification. Human merge and deployment remain required.
- **Code repository:** https://github.com/thanushreesuresh/SEOpilot
- **Original verified MVP commit:** [f66d76108a0f0fd3d11df2c2d0f9862f0be7f42d](https://github.com/thanushreesuresh/SEOpilot/commit/f66d76108a0f0fd3d11df2c2d0f9862f0be7f42d). Later security/configuration and allowance-interface changes are recorded in CHANGELOG; this earlier SHA does not include them. Organizer submission has not been performed.
- **Verified security/allowance implementation:** [3a90c3cd24662eb11bd6ea1067ea7a07a6c754f9](https://github.com/thanushreesuresh/SEOpilot/commit/3a90c3cd24662eb11bd6ea1067ea7a07a6c754f9), including [passing hosted checks](https://github.com/thanushreesuresh/SEOpilot/actions/runs/40120505329). This later documentation checkpoint records the result.
- **Verified v2 source:** [fbb94e2046212ce26469a46850d303bae92b387a](https://github.com/thanushreesuresh/SEOpilot/commit/fbb94e2046212ce26469a46850d303bae92b387a), with [passing hosted checks](https://github.com/thanushreesuresh/SEOpilot/actions/runs/40128792918). Four feature milestones and subsequent test corrections are preserved as separate commits. This documentation checkpoint contains no later implementation changes.
- **Working demo:** Follow the README's local setup and three-minute demonstration at http://localhost:3000.
- **Verified saved-evidence improvements:** [39b31e5dd58670b92b4bafcb83f2a995784323a9](https://github.com/thanushreesuresh/SEOpilot/commit/39b31e5dd58670b92b4bafcb83f2a995784323a9) passed [hosted checks](https://github.com/thanushreesuresh/SEOpilot/actions/runs/40132659834): 465 backend tests, 23 browser scenarios and static/build/contract checks. Adds saved comparisons, Markdown/CSV/JSON reports and bounded JSON-LD diagnostics. Recorded at 2026-10-25T02:38:32+05:30; earlier v2 SHA does not include these changes. Human review remains pending.
- **Access requirements:** Node.js 22+, Python 3.13+, local loopback services. Deterministic audits/samples need no credentials. Repository publication requires the private GitHub App and owner-installed workflow.

## Participants and event status

Participant names and event eligibility have not been supplied or verified. The repository owner is not automatically assumed to be the participant. Implementation uses actual 24–25 October 2026 timestamps and does not claim development took place during the 10–11 October event.

## Run and demonstrate

Install from the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -c backend/requirements.lock -e "backend[dev]"
npm --prefix repository-tools ci --ignore-scripts
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

Demonstrate a labelled sample, inspect evidence/severity filters, approve/reject and copy a recommendation, reopen history, then perform a bounded real audit. Recommendation approval records content review without publication.

For v2, follow [App setup](docs/github-app-setup.md) and [owner workflow installation](validation/README.md). Connect the owned repository/site, finish a live audit, select up to three static pages, prepare approved or entered metadata, inspect/download the diff, then separately approve **Create draft PR**. Review hosted checks, manually merge/deploy, acknowledge deployment and choose **Verify live**. Blocked/missing/truncated evidence stays unresolved; merge alone never proves deployment.

The confirmed pilot is [thanushree-portfolio](https://github.com/thanushreesuresh/thanushree-portfolio) at [thanushree-portfolio-six.vercel.app](https://thanushree-portfolio-six.vercel.app/). The three GitHub App settings remain unconfigured. Pilot PR, owner workflow, manual merge/deployment and successful live verification remain required for end-to-end release acceptance.

Use the blank `backend/.env.example` template and put your future key only in ignored `backend/.env`. Model: `gpt-6-luna`. The README lists the server kill switch, global call/output limits, database and private proxy-token configuration. Three accepted live audits per IP per rolling 24 hours, duplicate reuse and durable paid-call reservations protect local use. Samples and the smoke-test command make zero paid calls. Secrets are not included in this repository.

GitHub App credentials stay server-side; private source stays outside OpenAI requests. Patches add zero AI calls and are limited to three pages, five files and 100 changed lines. Two draft-PR publications are allowed per rolling 24 hours and one active fix per project. Private source expires after 24 hours with immediate deletion controls. GitHub Actions usage is separate from OpenAI usage; merge/deployment remain manual.

**Validation:** All 465 backend tests, 34 AST tests, seven validator tests, seven proxy tests and 23 hosted browser scenarios passed on the saved-evidence source identified above. Ruff, ESLint, TypeScript, production build, generated-contract drift and credential/history checks passed. The hosted mobile screenshot was inspected. Saved-report smoke checks preserved existing rows/counters. The latest local dashboard build still needs a manual process restart because automatic approval review blocked that action; the API remains running. Earlier live HTML, scoring and AI observations remain documented separately. Human review and the owned pilot's App/PR/deployment acceptance are pending. See [verification details](docs/verification.md), [architecture](docs/architecture.md), [README](README.md), [AI usage](AI_USAGE.md) and [change log](CHANGELOG.md).

**Deferred:** Search Console, public hosting/authentication, automatic merging/deployment, recurring audits, additional frameworks/sources and reliable orphan detection. No traffic, ranking, search-volume or other unavailable measurements are fabricated. Sources/dependencies are linked in README.

## Honest delivery checklist

- [x] Project description, repository and local demonstration instructions provided.
- [x] Core implementation and actual validation documented.
- [x] Codex contributions recorded; human review pending.
- [x] Secrets and local database files excluded from source control.
- [x] Rendered desktop/mobile browser verification completed on GitHub-hosted Chromium.
- [ ] Owned pilot completed through reviewed PR, hosted checks, manual deployment and live verification.
- [x] Live AI integration verified with user-supplied credentials; bounded results and limits recorded.
- [ ] Participant details and event eligibility verified.
- [ ] Organizer submission performed through its announced method and timing.

The original [event rules](RULES.md) remain preserved. This file records technical delivery readiness, not organizer acceptance.
