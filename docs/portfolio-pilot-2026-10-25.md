# Real portfolio pilot — 25 October 2026

Recorded 2026-10-25T06:41:05+05:30. This is a real live audit and an owner-approved draft PR, not a completed production deployment. Human merge/deployment and release review remain pending.

## Live evidence

Production origin: `https://thanushree-portfolio-six.vercel.app`. Audit `6c0571f7-8b06-4d85-bf8f-9203dd988b5c` assessed **eight HTTP-success HTML pages** and recorded **12 observations**, with a historical score of **84**. It made 11 budgeted request attempts at a 750 ms minimum interval. Coverage is partial: one PDF is excluded from assessment, and an extracted field reached its retention limit. No ranking or traffic improvement is established.

- All eight HTML pages shared `Thanushree Suresh | Digital Workshop` and the same description: two grouped duplicate findings.
- All eight pages lacked canonical tags: eight low-severity observations requiring contextual review.
- The inspected `/robots.txt` and `/sitemap.xml` returned HTTP 404: two low-severity site observations. An absent file alone does not establish a ranking penalty.
- No HTTP-error HTML page or confirmed broken internal link was observed in this bounded URL set. Unchecked destinations remain unchecked.

The first system-DNS attempt, audit `d5b4ba49-26b0-4e88-a734-4df5cadda5cc`, failed closed because the local resolver returned reserved NAT64 IPv6 translations alongside public IPv4 records. Its failed evidence remains saved. The successful run explicitly used the local Google DoH option, querying A and AAAA separately with DNSSEC checking enabled and client-subnet disclosure disabled. Google's AAAA answer was empty; returned public IPv4 addresses still passed the normal restrictions and pinned-TLS transport. The system resolver's protections were not relaxed. See the [provider specification](https://developers.google.com/speed/public-dns/docs/doh/json).

## Approved source change

Project mapping `fbfa0c77-ebaf-4efb-84e5-688de67a4641` binds the confirmed production origin to repository `1348533178`, `thanushreesuresh/thanushree-portfolio`, base branch `main`, with a blank application subdirectory.

The owner inspected and explicitly approved proposal `0baeee50-0aaf-4269-ba07-5c14c19de793` and patch hash `98691dcb64b6cf5f30cc931b73365e694a344993baf964e4be03d2a0b7ab14ce`. [Draft PR #1](https://github.com/thanushreesuresh/thanushree-portfolio/pull/1) contains one commit, [`512001fa1e26a77eb37cddee59f2808345d07306`](https://github.com/thanushreesuresh/thanushree-portfolio/commit/512001fa1e26a77eb37cddee59f2808345d07306), on `seopilot/0baeee50-0aaf-4269-ba07-5c14c19de793`. Its sole parent is the frozen base `193eb61222d1ee695077cdbff095c50de0ca1db1`; exact file blob hashes and the single-file change were verified after publication.

Only `app/page.tsx` gains six lines defining page-specific metadata:

```typescript
export const metadata = {
  title: "Thanushree Suresh | Flutter & AI Developer",
  description: "Explore Thanushree Suresh's portfolio of Flutter apps, AI platforms, and web projects, with case studies, skills, achievements, and contact details.",
};
```

The wording describes retained public-page evidence and makes the home metadata distinct. It does not resolve duplicates between the seven project pages. Dynamic project routes remain manual. Shared layouts, canonical/indexing directives, robots/sitemap files, content, dependencies and workflows were not changed. Private source was processed locally; zero OpenAI calls occurred.

## Validation and remaining gates

GitHub reports the PR as open, draft, unmerged, one commit, one file and six additions. The Vercel status for the exact head commit is success, and its bot reported the [preview deployment Ready](https://vercel.com/thanushree-sureshs-projects/thanushree-portfolio/491KK5jnvduHQyoSmwVnvayMgwiP). This is hosting-provider build evidence, not SEOPilot's configured validation result or proof of production deployment.

The preview audit `f54bd8ad-6cbd-4597-8006-25ea4cce94bd` stopped with zero assessed pages when its policy request redirected off-origin. No authentication/robots/origin barrier was bypassed. Its score is null and it cannot support an improvement claim.

The portfolio's configured `seopilot-validation.yml` is absent, with no observed GitHub workflow runs for the proposal commit. The saved fix run therefore has validation **unavailable**, not passed. The owner must review and install the [five workflow/harness files](../validation/README.md) on the portfolio base branch and obtain matching-commit build/render evidence. A local ignored ZIP of those exact five files was prepared for handoff; SEOPilot's App cannot write workflow files. Changing the base branch also makes the original proposal stale for a new publication; inspect/reconcile the existing PR and generate a fresh proposal if rebasing changes its approved commit.

After checks and human review, manually merge/deploy, then perform protected live verification of the original recorded URLs and expected metadata. The original production score remains 84; no post-deployment score or SEO gain is claimed. The seven project-page duplicates, eight canonical observations and missing policy files remain unresolved pending separate authorized work.

## Developer execution and checks

The owner clarified that the three-audits/IP limit applies to public HTTP users; local developers have no daily deterministic-audit allowance. The new local command records actual runs in the existing SQLite history, never adds/removes public admissions, disables AI and uses the existing cancellation-aware processor. It retains the five-active-run capacity and normal per-crawl bounds. No developer flag, header or exemption was added to the API or dashboard.

```powershell
.\.venv\Scripts\python.exe -m seopilot.developer_audit https://thanushree-portfolio-six.vercel.app/ --reason "Owner-requested portfolio SEO pilot" --pages 15 --depth 2 --dns google
```

Public admissions remained **3**, paid request reservations **6** (14 remaining from the configured 20), and earlier audit/decision records were preserved. The approved draft publication used one of the two publication reservations. No counter was reset or backdated.

Checks: **623 backend tests passed locally in 68.99 seconds**, including 25 new developer/DNS cases; 34 AST, seven validator and seven proxy cases passed. Repository Ruff, frontend ESLint and TypeScript checks passed. The existing Starlette/httpx deprecation and Node test-runner warnings remain. Two independent review axes found no outstanding issues after a cancellation regression was corrected.

Hosted follow-up at 2026-10-25T06:48:36+05:30: SEOPilot source [`e5928af`](https://github.com/thanushreesuresh/SEOpilot/commit/e5928afa66071f25ff44e06b6c62cf8d6668db57) passed [all hosted checks](https://github.com/thanushreesuresh/SEOpilot/actions/runs/40149886193), including 623 backend tests (31.08 seconds), 46 browser scenarios (41.2 seconds), helpers, lint/types/build, contract drift and credential/history checks. These are SEOPilot fixtures and build evidence, not the missing portfolio validator or a deployed SEO result. No additional website/AI calls or production changes were made for this documentation checkpoint. Human release review remains pending.
