# Dashboard design reference

The primary concept was generated with the built-in ImageGen tool and saved as `dashboard-concept.png` (1536 × 1024). It is a design reference, not a screenshot of a running or deployed product.

## Extracted system

- True-white main surface; cool gray sidebar; fine pale-gray borders; pine primary controls and selected states.
- Desktop: 240 px persistent sidebar, 40 px main gutters, editorial headline, one bordered audit form, one shared metric strip, table plus attached evidence inspector.
- System sans-serif typography; approximately 51 px primary heading, 20 px section title, 12–14 px table and control content; restrained 6–8 px corner radii.
- Compass/navigation icon, home/history navigation icons, link icon, disclosure arrows, search, check/reject, copy and information icons. Icons are code-native controls.
- Mobile: sidebar becomes a compact top navigation; inputs and actions wrap; metrics form two rows; the evidence inspector follows the bounded table, preserving all controls.

## Allowed copy and functional additions

Primary concept copy: SEOPilot; Overview; Audit history; Workspace; Local workspace; Your next move in search.; Turn your website into a clear, prioritized action plan.; Start with your website; Run audit; Add business context; Explore sample audit; Read-only crawling. Every recommendation stays in your hands.; Audit overview; Sample audit; SEO health; Pages assessed; Issues found; Ready for review; Issues; Recommendations; Pages; All severities; All categories; Search URLs; Evidence; Suggested fix; Copy suggestion; Approve; Reject; Coverage matters.

Intentional additions needed by the implementation: crawl settings; clearly labelled fixture disclosure; actual dates and counts; severity breakdown; audit summary; extraction limits; score explanation; AI availability; persisted decision timestamp; website-not-modified note; progress and service errors; empty state; history table; explanatory button/field accessible names. Example rows and metrics in the concept are replaced by actual API results. Empty workspace displays no simulated metrics. Detail copy uses the backend finding explanations rather than the short illustrative concept copy.

## Verification record

- Frontend ESLint: passed without warnings.
- Frontend TypeScript: passed.
- Native browser screenshots and final fidelity comparison: pending root-agent QA.
