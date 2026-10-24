# Owner-installed validation

This template runs an owned Next.js proposal on a disposable GitHub-hosted Ubuntu VM. SEOPilot does not install it or modify workflows. The owner must review and commit it before publishing a fix PR. Repository CI and preview automation may incur GitHub Actions or hosting usage independently of OpenAI limits.

1. Copy `seopilot-validation.yml` to your website repository's `.github/workflows/seopilot-validation.yml`.
2. Copy `package.json`, `package-lock.json`, `lib.mjs` and `run.mjs` from this folder to that repository's `.seopilot/validation/`.
3. Commit these files to the selected base branch. Set SEOPilot's configured validation workflow to `seopilot-validation.yml`.
4. Review a SEOPilot patch, explicitly publish its draft PR, and use the validation status action in SEOPilot. No repository secrets are required for this template.

The workflow only accepts same-repository draft PRs from `seopilot/` branches. It checks out the validator from the exact base commit and the website from the exact PR head commit. Actions are pinned to full commit SHAs, Node is pinned to 22.17.0, and Playwright 1.55.1 pins its Chromium revision through the committed lockfile. Checkout credentials are not persisted; job permissions are `contents: read`; the deadline is ten minutes. Never change this job to `pull_request_target`, a self-hosted runner, or add OpenAI/App keys, database files, or production secrets.

The trusted runner parses the JSON block in the PR body without shell interpolation. It runs `npm ci` in the frozen application subdirectory and requires `package-lock.json` plus a declared production `build` script. Declared `lint`, `typecheck` (or `type-check`) and `test` scripts run with deadlines; absent scripts are reported as skipped. Script processes receive a minimal environment. Build and configuration code execute only inside the disposable GitHub VM. Sites requiring private npm credentials or secret-backed builds will fail until their owner supplies an independently reviewed validation strategy; do not copy production secrets into this template.

Chromium starts the built Next.js app on `127.0.0.1:4173` and requests only its loopback origin. Each of at most three pages must return HTTP 2xx, contain at least 40 visible characters, preserve the approved title, description, canonical and indexing directives, and produce no browser console or runtime errors. External browser requests are blocked; sites dependent on third-party resources can fail conservatively. A viewport screenshot and bounded JSON report are uploaded for one day. Raw source and script output are omitted from the artifact. Failed install/build/render checks remain failed; the app does not repair or automatically rerun them.

The backend checks the authorized workflow and commit through GitHub's API before downloading its artifact. Artifact validation then checks proposal ID, patch hash, commit and run IDs, the full frozen page set, check completeness, rendered values, ZIP entry paths and size limits. Artifacts are read in memory without extraction. This is evidence from the owner's CI, not a sandbox protecting the owner from intentionally malicious source code: repository code controls its own build and runs only in an isolated hosted job without SEOPilot credentials.

Run parser and comparison unit tests locally (these do not launch a browser or execute website code):

```powershell
npm ci --ignore-scripts
npm test
```

The complete browser/build acceptance test runs after the owner installs the template and publishes an approved draft PR. Passing this hosted check proves the proposed source rendered as expected; it does not prove deployment. Use **Verify live** after manually deploying the merged changes.

Sources: [GitHub Actions security guidance](https://docs.github.com/en/actions/reference/security/secure-use), [workflow artifacts](https://docs.github.com/en/actions/tutorials/store-and-share-data), [Playwright browser installation](https://playwright.dev/docs/browsers), and [Next.js metadata](https://nextjs.org/docs/app/api-reference/functions/generate-metadata).
