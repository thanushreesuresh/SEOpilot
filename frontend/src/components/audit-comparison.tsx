import { useEffect, useRef, useState } from "react";
import { ArrowRight, GitCompareArrows, Search } from "lucide-react";
import { dateTime, type AuditSummary } from "@/lib/api";
import { reportingApi, type AuditComparison, type FindingChange } from "@/lib/reporting-api";
import { ExternalUrl, Notice, Severity, Spinner } from "./ui";

type ChangeStatus = FindingChange["status"];
const statuses: ChangeStatus[] = ["added", "persistent", "resolved", "unresolved_unknown"];
const statusLabels: Record<ChangeStatus, string> = { added: "Added", persistent: "Persistent", resolved: "Resolved", unresolved_unknown: "Unresolved / unknown" };
const finishedStatuses = new Set(["completed", "partial", "failed", "interrupted", "cancelled"]);

function origin(url: string): string {
  try { return new URL(url).origin; } catch { return ""; }
}
function isLaterMatch(before: AuditSummary, after: AuditSummary): boolean {
  const site = origin(before.url);
  return before.id !== after.id && !!site && site === origin(after.url) && before.mode === after.mode && Date.parse(before.created_at) < Date.parse(after.created_at);
}
function auditLabel(audit: AuditSummary): string {
  return `${dateTime(audit.created_at)} · ${origin(audit.url)} · ${audit.mode === "demo" ? "sample" : "live"} · ${audit.status} · ${audit.id.slice(0, 8)}`;
}

export function AuditComparisonPanel({ history }: { history: AuditSummary[] }) {
  const finished = history.filter((item) => finishedStatuses.has(item.status)).sort((a, b) => Date.parse(a.created_at) - Date.parse(b.created_at));
  const initialBefore = finished.find((item) => finished.some((later) => isLaterMatch(item, later)));
  const [beforeId, setBeforeId] = useState(initialBefore?.id ?? "");
  const [afterId, setAfterId] = useState(() => initialBefore ? finished.filter((item) => isLaterMatch(initialBefore, item)).at(-1)?.id ?? "" : "");
  const [result, setResult] = useState<AuditComparison | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);
  const before = finished.find((item) => item.id === beforeId);
  const later = before ? finished.filter((item) => isLaterMatch(before, item)) : [];
  const after = later.find((item) => item.id === afterId);

  function changeBefore(id: string) {
    setBeforeId(id); setResult(null); setError("");
    const selected = finished.find((item) => item.id === id);
    setAfterId(selected ? finished.filter((item) => isLaterMatch(selected, item)).at(-1)?.id ?? "" : "");
  }
  async function compare(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!before || !after) return;
    controller.current?.abort();
    const abort = new AbortController();
    controller.current = abort;
    setPending(true); setError(""); setResult(null);
    try {
      const comparison = await reportingApi.compare({ before_audit_id: before.id, after_audit_id: after.id }, abort.signal);
      if (!abort.signal.aborted) setResult(comparison);
    } catch (cause) {
      if (!abort.signal.aborted) setError(cause instanceof Error ? cause.message : "Could not compare these audits. Try again.");
    } finally {
      if (!abort.signal.aborted) setPending(false);
    }
  }

  return <section className="comparison-panel" id="audit-comparison" aria-labelledby="comparison-heading">
    <div className="comparison-heading"><div><span className="project-eyebrow">Saved audit evidence</span><h2 id="comparison-heading"><GitCompareArrows size={20} aria-hidden="true" />Compare audits</h2></div><span className="comparison-cost">No new crawl or AI calls</span></div>
    <p className="comparison-intro">Choose an earlier and later finished audit of the same origin and mode. The latest 100 audits in this workspace are available.</p>
    <form className="comparison-form" onSubmit={(event) => void compare(event)}>
      <label>Earlier audit<select value={before?.id ?? ""} onChange={(event) => changeBefore(event.target.value)} disabled={pending || !finished.length} required><option value="">Choose an earlier audit</option>{finished.map((item) => <option key={item.id} value={item.id}>{auditLabel(item)}</option>)}</select></label>
      <ArrowRight size={18} className="comparison-arrow" aria-hidden="true" />
      <label>Later audit<select value={after?.id ?? ""} onChange={(event) => { setAfterId(event.target.value); setResult(null); setError(""); }} disabled={pending || !later.length} required><option value="">Choose a later audit</option>{later.map((item) => <option key={item.id} value={item.id}>{auditLabel(item)}</option>)}</select></label>
      <button className="button button-primary" disabled={pending || !before || !after}>{pending ? <Spinner size={15} /> : <GitCompareArrows size={15} aria-hidden="true" />}{pending ? "Comparing…" : "Run comparison"}</button>
    </form>
    {!initialBefore ? <p className="comparison-empty">No matching pair is available. Compare after two finished audits of the same origin and mode have been saved.</p> : before && !later.length ? <p className="comparison-empty">There is no later finished audit for this origin and mode. Choose another earlier audit.</p> : null}
    {error ? <Notice variant="error">{error}</Notice> : null}
    {pending ? <p className="comparison-progress" role="status">Comparing saved findings and assessed page coverage…</p> : null}
    {result ? <ComparisonResults key={`${result.before_audit_id}:${result.after_audit_id}`} result={result} sample={before?.mode === "demo"} /> : null}
  </section>;
}

function ComparisonResults({ result, sample }: { result: AuditComparison; sample: boolean }) {
  const [status, setStatus] = useState<ChangeStatus | "">("");
  const [query, setQuery] = useState("");
  const changes = statuses.flatMap((name) => result[name]);
  const filtered = changes.filter((item) => (!status || item.status === status) && item.url.toLowerCase().includes(query.toLowerCase()));
  const showDelta = result.versions_match && result.coverage_comparable && result.score_delta !== null;
  return <div className="comparison-results" aria-label="Audit comparison results">
    <div className="comparison-result-heading"><h3>{result.origin}</h3>{sample ? <span className="sample-badge">Sample comparison</span> : null}</div>
    {sample ? <p className="comparison-intro">These results compare saved sample data. They do not describe a live website change.</p> : null}
    <div className="comparison-score"><div><span>Earlier health</span><strong>{result.score_before ?? "—"}<small> /100</small></strong></div><ArrowRight size={17} aria-hidden="true" /><div><span>Later health</span><strong>{result.score_after ?? "—"}<small> /100</small></strong></div><div className="comparison-delta"><span>Comparable score change</span><strong>{showDelta ? `${result.score_delta! > 0 ? "+" : ""}${result.score_delta}` : "Unavailable"}{showDelta ? <small> points</small> : null}</strong></div></div>
    <p className="comparison-intro">{result.score_delta_reason} Health scores describe technical checks; they do not predict ranking or traffic changes.</p>
    <div className="comparison-counts" aria-label="Finding change counts">{statuses.map((name) => <button key={name} className={`comparison-count ${status === name ? "selected" : ""}`} aria-pressed={status === name} onClick={() => setStatus(status === name ? "" : name)}><strong>{result.counts[name]}</strong><span>{statusLabels[name]}</span></button>)}</div>
    <p className="comparison-intro">Unresolved / unknown findings lack comparable follow-up evidence. A page excluded from the later audit is not counted as fixed.</p>
    <div className="comparison-filters"><label>Change status<select value={status} onChange={(event) => setStatus(event.target.value as ChangeStatus | "")}><option value="">All changes</option>{statuses.map((name) => <option key={name} value={name}>{statusLabels[name]}</option>)}</select></label><div className="search-field"><Search size={15} aria-hidden="true" /><label className="sr-only" htmlFor="comparison-url-search">Filter comparison URLs</label><input id="comparison-url-search" type="search" placeholder="Filter URLs…" value={query} onChange={(event) => setQuery(event.target.value)} /></div></div>
    {filtered.length ? <div className="table-scroll comparison-table-scroll" tabIndex={0} aria-label="Finding changes"><table className="comparison-table"><thead><tr><th>Change</th><th>Finding</th><th>Severity</th><th>Page and evidence</th></tr></thead><tbody>{filtered.map((change) => <tr key={`${change.status}:${change.stable_id}`}><td><span className={`comparison-status comparison-status-${change.status}`}>{statusLabels[change.status]}</span></td><td><strong>{change.title}</strong><span className="comparison-rule">{change.rule_id} · {change.field || "Page"}</span></td><td><Severity value={change.severity} /></td><td><ExternalUrl url={change.url}>{change.url}</ExternalUrl>{change.is_site ? <span className="comparison-rule">Site-wide finding</span> : null}<p>{change.reason}</p><span className="comparison-rule">Later evidence: {change.after_state}</span></td></tr>)}</tbody></table></div> : <p className="comparison-empty" role="status">{status || query ? "No finding changes match these filters." : "No finding changes were identified in the compared evidence."}</p>}
    <details className="comparison-detail"><summary>Coverage, versions, and excluded pages</summary><p>Only assessed pages provide comparable evidence. Blocked, failed, unchecked, removed, or limited pages can leave findings unresolved.</p>
      <div className="table-scroll"><table className="comparison-coverage-table"><caption>Audit coverage and check versions</caption><thead><tr><th>Measure</th><th>Earlier</th><th>Later</th></tr></thead><tbody><tr><th>Rules version</th><td>{result.rules_version_before}</td><td>{result.rules_version_after}</td></tr><tr><th>Score version</th><td>{result.score_version_before}</td><td>{result.score_version_after}</td></tr>{(["attempted", "assessed", "blocked", "failed", "unchecked"] as const).map((field) => <tr key={field}><th>{field[0].toUpperCase() + field.slice(1)} pages</th><td>{result.coverage_before[field]}</td><td>{result.coverage_after[field]}</td></tr>)}<tr><th>Crawl limits reached</th><td>{result.coverage_before.truncated ? "Yes" : "No"}</td><td>{result.coverage_after.truncated ? "Yes" : "No"}</td></tr></tbody></table></div>
      <p>Versions {result.versions_match ? "match" : "differ"}. Assessed page coverage is {result.coverage_comparable ? "comparable" : "not comparable"}.</p>
      <UrlList label="Common assessed URLs" urls={result.common_assessed_urls} /><UrlList label="Newly assessed URLs" urls={result.added_assessed_urls} /><UrlList label="Removed from assessed coverage" urls={result.removed_assessed_urls} />
    </details>
    {result.limitations.length ? <div className="comparison-limitations"><h4>Comparison limitations</h4><ul>{result.limitations.map((item, index) => <li key={index}>{item}</li>)}</ul></div> : null}
  </div>;
}

function UrlList({ label, urls }: { label: string; urls: string[] }) {
  return <details className="comparison-url-list"><summary>{label} ({urls.length})</summary>{urls.length ? <ul>{urls.map((url) => <li key={url}><ExternalUrl url={url}>{url}</ExternalUrl></li>)}</ul> : <p>No URLs in this group.</p>}</details>;
}
