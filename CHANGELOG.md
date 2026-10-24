# Change log

Record each meaningful project change during the event, newest first. Update this file in the same commit as the change. Use a real timestamp with timezone, for example `YYYY-MM-DDTHH:MM:SS+05:30`.

## Event build log

## 2026-10-24T22:30:24+05:30 — Audit extracted evidence and explain health scoring

- Changed: Added reusable deterministic SEO rules, duplicate grouping, evidence-bearing findings, actionable rule recommendations, configurable editorial thresholds, and page-normalized scoring.
- Why: Produce explainable observations without relying on AI or inventing unavailable coverage or performance data.
- Validation: 18 focused rule tests passed; scoped Ruff passed; reviewed unknown-page exclusion, duplicate deduplication, HTTP-error handling, and context-sensitive advice.
- Limitations: This milestone operates on extracted page models; crawler/API/dashboard integration follows. No orphan or search-performance claims are produced.

## 2026-10-24T22:16:33+05:30 — Add the local API and persistence foundation

- Changed: Added typed Pydantic audit contracts, SQLite projects/audits/pages/issues/recommendations/decision records, queue recovery, loopback API guards, OpenAPI export, and backend dependency configuration. Added reproducible setup instructions and local-data ignore rules.
- Why: Establish a durable, reviewable foundation for the approved website-to-audit workflow while preserving the original remote history.
- Validation: Isolated backend dependencies installed; 5 storage/API contract tests passed; scoped Ruff checks and `git diff --check` passed. Reviewed parameterized queries, body/origin guards, queue transactions, and restart handling.
- Limitations: Crawler, rules, AI, and dashboard are subsequent milestones. Starlette emits one upstream HTTPX TestClient deprecation warning. No live AI calls made. Human review pending.

No project implementation has been recorded yet. Replace this sentence with entries as you build:

```text
## <actual timestamp> — <short change title>

- Changed: <feature or files changed>
- Why: <reason for the change>
- Validation: <commands or manual checks actually run, with results>
- Limitations: <known issues or "None identified in these checks">
```

## Template setup — 10 October 2026

- Changed: Added the event README, rules, agent guide, change log, AI usage record, submission checklist, Git ignore rules, and pull request checklist.
- Why: Give participants a consistent starting point for event rules, basic coding patterns, documented changes, and regular commits.
- Validation: Checked local Markdown links, event detail consistency, required documents, and diff whitespace before publishing.
- Limitations: Documentation scaffolding only; no participant project, application, or working demo is included. GitHub publication and template status are verified separately after creation.
