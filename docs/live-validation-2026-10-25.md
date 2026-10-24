# Live SEO and AI verification — 25 October 2026 (IST)

Recorded at 2026-10-25T00:18:56+05:30. These are bounded samples, not complete site audits or search-ranking measurements. The user supplied the existing ignored backend key and authorized live calls. No credential values, raw HTML, IP identities or private proxy tokens are included here.

## Observed results

| Target | Assessed pages | Findings | Internal score | AI result |
| --- | --- | --- | --- | --- |
| [Python homepage](https://www.python.org/), [About](https://www.python.org/about/), [Applications](https://www.python.org/about/apps/) | 3 | 8 | 89 | Generation and independent model review completed; 3 description suggestions published as inferred, pending human decisions |
| [Example Domain](https://example.com/) | 1 | 6 | 82 | Initial AI stage failed safely; deterministic findings remained available |
| Example Domain transport recheck | 1 | 6 | 82 | Connection failure reproduced; after TLS fix, generation returned HTTP 200 and valid structured output. Review was blocked by the existing per-audit allowance, so no unreviewed suggestions published |

Python's overall audit is **partial**: three pages were assessed successfully, but page/depth limits left 63 discovered URLs unchecked, and visible-text excerpts reached their retention bound. No blocked or failed page is hidden. Example's partial status reflects its AI failure/allowance state, not a failed HTML fetch.

## Independent evidence checks

All three Python pages returned HTTP 200 over HTTPS. A separate raw-HTML fetch and Beautiful Soup inspection matched each saved title, meta description, canonical absence and all retained H1 values. Titles were 21, 26 and 36 characters; all descriptions were 52 characters. H1 counts were 5, 1 and 7.

- The shared description finding affects all three pages. Each accepted AI proposal describes its particular page, references supplied evidence and has Medium priority. Independent review found no invented business facts, performance metrics or ranking promises. Suggested description lengths were 127, 138 and 149 characters.
- The homepage's multiple H1s belong to its carousel. This is contextual review guidance, not proof of ranking harm. Missing canonicals likewise do not prove duplicate-indexing trouble.
- The default Python sitemap location returned 404 and robots.txt declared no sitemap. The finding is limited to inspected locations; other sitemap locations may exist.
- Example Domain returned HTTP 200 with a 14-character title and no meta description, H1 or canonical in the inspected HTML. Its inspected robots.txt and sitemap.xml returned 404. These observations support its six rules, but optimization has little practical value for a documentation placeholder.

Independent score arithmetic: Python page penalties are 9, 7 and 11; their mean is 9, plus a 2-point site penalty: `100 - 9 - 2 = 89`. Example has 14 page points plus 4 site points: `100 - 14 - 4 = 82`. These are the application's documented heuristics, not Google scores or predictions.

## Live failure and correction

The original Example failure exposed only a sanitized fallback message, so its exact cause cannot be retrospectively proven. A subsequent instrumented recheck raised `APIConnectionError` without an HTTP response. A separate unauthenticated SDK probe reproduced `SSLCertVerificationError` with the default trust bundle; a verified OS-default SSL context reached OpenAI with HTTP 401 as expected without credentials.

The AI transport now uses `ssl.create_default_context()`, matching the crawler's system trust policy. Certificate validation and hostname checks remain enabled; environment proxies and SDK retries remain disabled. No certificate checks were bypassed and no unverified certificate was installed.

After correction, authenticated lookup confirmed access to `gpt-6-luna`. A budgeted generation request returned HTTP 200, completed status and valid structured output: 1,258 input tokens and 984 output tokens (including 146 reasoning tokens), 2,242 total. Those usage figures cover that one response only, not the complete session or an invoice. Its audit had already consumed one reservation; generation consumed the second, so the review reservation was denied. The unreviewed suggestions were correctly withheld.

One diagnostic wrapper also failed locally before network access due to its instrumentation order. Its reservation was retained; the wrapper was corrected in a temporary process and was not added to application source. No counters were refunded or reset.

## Spending, persistence and credential checks

- Three admitted test audits consumed the local IP allowance. A fourth distinct submission, even with forged `X-Forwarded-For`, returned HTTP 429 with `Retry-After`. The next slot returns at **2026-10-26 00:03:28 IST**.
- An identical recent audit returned HTTP 202 with `X-Audit-Reused: true`, without another admission or AI reservation. An unauthenticated private client-IP header returned HTTP 403.
- Six durable AI reservations were retained: the Python generation/review, the initial Example failure, one local diagnostic failure, the connection recheck and the successful post-fix generation. Fourteen of the default 20 reservations remained. Reservations include failed/local attempts and are not a billed-request count.
- Saved Python results and all three pending AI review decisions survived a backend restart. No website changes or automatic human approvals occurred.
- Checked API responses did not contain the configured key. `backend/.env`, SQLite, tokens and raw audit snapshots remain ignored and untracked. The key was neither rewritten nor printed.

Raw bounded snapshots/diagnostic metadata remain only under ignored `backend/.data/live-verification/` and in the local SQLite history. Python audit ID: `016182fb-aad7-41e8-8c81-efdd724e2fef`. No complete HTML is retained.

## Regression checks and remaining limits

The TLS regression failed before the fix and passed afterward. **207 offline backend tests and Ruff passed.** pytest now disables dotenv loading and masks inherited OpenAI keys before application modules are imported, so routine tests cannot use the developer's real key. SDK tests explicitly provide harmless fakes.

Frontend source/contracts did not change in this verification. The production dashboard and secure backend were restarted with current code. Prior frontend build, type/lint, six proxy tests and hosted checks remain recorded in [verification](verification.md); no new rendered desktop/mobile pass is claimed because the managed browser-origin denial remains in effect. Full new Example generation-plus-review was not repeated after its per-audit allowance was spent. Public hosting, Search Console and search-performance validation remain outside this local test. Human review is pending.
