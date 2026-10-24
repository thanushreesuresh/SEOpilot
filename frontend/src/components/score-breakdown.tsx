import type { Audit } from "@/lib/api";
import { pagePath } from "@/lib/api";
import { ExternalUrl } from "./ui";

function number(value: number | null) {
  return value === null ? "unavailable" : value.toLocaleString("en-US", { maximumFractionDigits: 4 });
}

export function ScoreBreakdownDetails({ audit, onSearch }: { audit: Audit; onSearch: (url: string) => void }) {
  const detail = audit.score.breakdown;
  if (!detail) return <div className="score-breakdown"><p>A score breakdown was not recorded; the historical score has not been recalculated.</p></div>;
  return <section className="score-breakdown" aria-label="Score deductions">
    <h4>{audit.mode === "demo" ? "Sample score calculation" : "Recorded score calculation"}</h4>
    {audit.score.value === null ? <p>No assessed pages means no score. Excluded pages do not improve the denominator.</p> : <>
      <dl className="score-totals"><div><dt>Mean page penalty</dt><dd>{number(detail.mean_page_penalty)}</dd></div><div><dt>Site penalty</dt><dd>{detail.site_penalty} / 20</dd></div><div><dt>Before rounding</dt><dd>{number(detail.unrounded_value)}</dd></div></dl>
      <p>100 − mean page penalty − site penalty = {number(detail.unrounded_value)} → {audit.score.value} / 100. Values here display up to four decimal places. The saved score rounds to the nearest integer, with ties to even, then clamps to 0–100.</p>
      <p>Each rule counts once per affected page. Raw points are capped at 100 per page; HTTP-error pages receive 100 regardless of rule totals. Page penalties are averaged across {audit.score.assessed_pages} assessed pages.</p>
      <div className="score-page-list">{detail.pages.map((page) => <details key={page.page_id}>
        <summary><span>{pagePath(page.url)}</span><strong>{page.penalty} / 100 page penalty</strong></summary>
        <p><ExternalUrl url={page.url}>{page.url}</ExternalUrl></p>
        <p>Raw rule points: {page.rule_points}. {page.outcome === "http_error" ? "HTTP-error override: the page penalty is 100." : `After the page cap: ${page.penalty}.`}</p>
        {page.rules.length ? <ul>{page.rules.map((rule) => <li key={rule.rule_id}><strong>{rule.title}</strong><span>{rule.severity} · {rule.points} raw points · <code>{rule.rule_id}</code></span></li>)}</ul> : <p>No page-rule deductions recorded.</p>}
        <button className="button button-small button-secondary" onClick={() => onSearch(page.url)}>Search this URL in findings</button>
      </details>)}</div>
      <h4>Site deductions</h4>
      <p>{detail.site_rule_points} raw site points → {detail.site_penalty} after the combined 20-point cap. Each site rule counts once.</p>
      {detail.site_rules.length ? <ul>{detail.site_rules.map((rule) => <li key={rule.rule_id}><strong>{rule.title}</strong><span>{rule.severity} · {rule.points} raw points · <code>{rule.rule_id}</code></span></li>)}</ul> : <p>No site-rule deductions recorded.</p>}
    </>}
    <h4>Excluded from the score denominator</h4>
    {detail.excluded_pages.length ? <ul>{detail.excluded_pages.map((page) => <li key={page.page_id}><ExternalUrl url={page.url}>{page.url}</ExternalUrl><span>{page.outcome.replaceAll("_", " ")} · HTTP {page.status_code ?? "not recorded"}</span></li>)}</ul> : <p>No fetched page records were excluded. Undiscovered URLs still remain outside this audit.</p>}
    <p>These deductions explain the recorded heuristic score. Fixes require fresh evidence; review decisions do not remove penalties or predict ranking or traffic gains.</p>
  </section>;
}
