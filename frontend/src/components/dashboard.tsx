"use client";
import { useCallback, useEffect, useState } from "react";
import { ArrowLeft, FileClock, GitPullRequest, House, LockKeyhole, RefreshCw } from "lucide-react";
import { api, dateTime, domain, isActive, type Audit, type AuditSummary, type Recommendation, type UsageStatus } from "@/lib/api";
import { AuditForm } from "./audit-form";
import { AuditResults } from "./audit-results";
import { Brand, Notice, Spinner, Status } from "./ui";
import { ProjectWorkspace } from "./project-workspace";

export default function Dashboard() {
  const [audit, setAudit] = useState<Audit | null>(null);
  const [history, setHistory] = useState<AuditSummary[]>([]);
  const [usage, setUsage] = useState<UsageStatus | null>(null);
  const [view, setView] = useState<"overview" | "history" | "projects">("overview");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState<"live" | "demo" | null>(null);
  const [error, setError] = useState("");
  const [pollError, setPollError] = useState("");
  const [notice, setNotice] = useState("");

  const refreshUsage = useCallback(async () => {
    try { setUsage(await api.usage()); }
    catch (cause) { setUsage(null); setError(cause instanceof Error ? cause.message : "Could not refresh your audit allowance."); }
  }, []);

  const refreshHistory = useCallback(async () => {
    const items = await api.history();
    setHistory(items);
  }, []);

  useEffect(() => {
    const abort = new AbortController();
    async function initialize() {
      const id = new URL(window.location.href).searchParams.get("audit");
      try {
        const [items, selected, allowance] = await Promise.all([api.history(abort.signal), id ? api.audit(id, abort.signal) : Promise.resolve(null), api.usage(abort.signal)]);
        if (!abort.signal.aborted) { setHistory(items); setAudit(selected); setUsage(allowance); }
      } catch (cause) { if (!abort.signal.aborted) setError(cause instanceof Error ? cause.message : "Could not load your workspace."); }
      finally { if (!abort.signal.aborted) setLoading(false); }
    }
    void initialize();
    return () => abort.abort();
  }, []);

  const id = audit?.id;
  const active = audit ? isActive(audit) : false;
  useEffect(() => {
    if (!id || !active) return;
    const abort = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const next = await api.audit(id!, abort.signal);
        if (abort.signal.aborted) return;
        setAudit(next); setPollError("");
        if (isActive(next)) timer = setTimeout(poll, 1000);
        else { void refreshHistory().catch(() => {}); void refreshUsage(); }
      } catch (cause) {
        if (!abort.signal.aborted) { setPollError(cause instanceof Error ? cause.message : "Connection interrupted. Retrying…"); timer = setTimeout(poll, 3000); }
      }
    }
    timer = setTimeout(poll, 1000);
    return () => { abort.abort(); clearTimeout(timer); };
  }, [id, active, refreshHistory, refreshUsage]);

  function remember(next: Audit) {
    setAudit(next); setView("overview"); setError(""); setPollError(""); setNotice("");
    const url = new URL(window.location.href); url.searchParams.set("audit", next.id); window.history.replaceState(null, "", url);
  }
  async function submit(url: string, business_context: string, page_limit: number, max_depth: number, allow_ai: boolean) {
    setSubmitting("live"); setError("");
    try { const result = await api.create({ url, business_context, allow_ai, options: { page_limit, max_depth } }); remember(result.audit); if (result.reused) setNotice("Opened your identical active or recent audit. No additional audit allowance or AI calls were used."); await refreshHistory(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Could not start the audit."); }
    finally { await refreshUsage(); setSubmitting(null); }
  }
  async function demo() {
    setSubmitting("demo"); setError("");
    try { remember(await api.demo()); await refreshHistory(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Could not create the sample audit."); }
    finally { setSubmitting(null); }
  }
  async function selectAudit(nextId: string) {
    setLoading(true); setError("");
    try { remember(await api.audit(nextId)); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Could not open this audit."); }
    finally { setLoading(false); }
  }
  function updateRecommendation(next: Recommendation) {
    setAudit((current) => current ? { ...current, recommendations: current.recommendations.map((item) => item.id === next.id ? next : item) } : current);
  }
  function switchView(next: "overview" | "history" | "projects") { setView(next); if (next !== "overview") void refreshHistory().catch((cause) => setError(cause instanceof Error ? cause.message : "Could not load audit history.")); }

  return <div className="app-shell">
    <a className="skip-link" href="#main-content">Skip to content</a>
    <aside className="sidebar">
      <Brand />
      <nav aria-label="Workspace navigation">
        <button className={`nav-item ${view === "overview" ? "selected" : ""}`} onClick={() => switchView("overview")} aria-current={view === "overview" ? "page" : undefined}><House size={18} />Overview</button>
        <button aria-label="Audit history" className={`nav-item ${view === "history" ? "selected" : ""}`} onClick={() => switchView("history")} aria-current={view === "history" ? "page" : undefined}><FileClock size={18} />Audit history{history.length ? <span className="nav-count">{history.length}</span> : null}</button>
        <button className={`nav-item ${view === "projects" ? "selected" : ""}`} onClick={() => switchView("projects")} aria-current={view === "projects" ? "page" : undefined}><GitPullRequest size={18} />Projects & fixes</button>
      </nav>
      <div className="sidebar-footer"><span><LockKeyhole size={13} />Local workspace</span><p>Human decisions.<br />Clear evidence.</p></div>
    </aside>
    <main id="main-content" className="main-content">
      <header className="topbar"><div>Workspace<span className="breadcrumb-divider">/</span><strong>{view === "history" ? "Audit history" : view === "projects" ? "Projects & fixes" : "Overview"}</strong></div><span className="workspace-label"><span className="online-dot" />Local workspace</span></header>
      <div className="page-content">
        {view === "overview" ? <>
          <section className="page-heading"><h1>Your next move in search.</h1><p>Turn your website into a clear, prioritized action plan.</p></section>
          <AuditForm onSubmit={submit} onDemo={demo} onRefreshUsage={async () => { setError(""); await refreshUsage(); }} submitting={submitting} active={active} initializing={loading} usage={usage} />
          {notice ? <Notice>{notice}</Notice> : null}
          {error ? <Notice variant="error">{error}</Notice> : null}
          {pollError ? <Notice variant="error">{pollError} Progress will reconnect automatically.</Notice> : null}
          {loading ? <div className="loading-surface" role="status"><Spinner />Loading your workspace…</div> : audit ? <AuditResults key={audit.id} audit={audit} onRecommendation={updateRecommendation} /> : <EmptyAudit onDemo={demo} disabled={!!submitting} />}
        </> : view === "projects" ? <ProjectWorkspace history={history} currentAudit={audit} /> : <>
          <section className="page-heading history-heading"><div><h1>Audit history</h1><p>A clear record of your website, findings, and decisions.</p></div><button className="button button-secondary" onClick={() => switchView("overview")}><ArrowLeft size={15} />Back to overview</button></section>
          {error ? <Notice variant="error">{error}</Notice> : null}
          <section className="history-panel" aria-label="Previous audits"><div className="section-head"><h2>Your audits <span className="count">{history.length}</span></h2><button className="button button-small button-secondary" onClick={() => void refreshHistory().catch((cause) => setError(cause.message))}><RefreshCw size={14} />Refresh</button></div>
            {history.length ? <div className="table-scroll"><table className="history-table"><thead><tr><th>Website</th><th>Started</th><th>Status</th><th>Pages</th><th>Issues</th><th>Health</th><th><span className="sr-only">Open</span></th></tr></thead><tbody>{history.map((item) => <tr key={item.id}><td><button className="history-link" onClick={() => void selectAudit(item.id)}>{domain(item.url)}</button><div className="muted table-caption">{item.mode === "demo" ? "Sample audit" : "Live audit"}</div></td><td className="muted">{dateTime(item.created_at)}</td><td><Status value={item.status} /></td><td>{item.pages}</td><td>{item.issues}</td><td><strong>{item.score ?? "—"}</strong>{item.score !== null ? <span className="muted"> /100</span> : null}</td><td><button className="button button-small button-secondary" onClick={() => void selectAudit(item.id)}>Open audit</button></td></tr>)}</tbody></table></div> : <div className="history-empty"><FileClock size={30} strokeWidth={1.3} /><h3>Your first audit starts here.</h3><p>Run an audit or explore the sample to see it in your history.</p><button className="button button-primary" onClick={() => switchView("overview")}>Start an audit</button></div>}
          </section>
        </>}
        <footer className="page-footer"><span>Made for better next steps.</span><span>SEOPilot · Local edition</span></footer>
      </div>
    </main>
  </div>;
}

function EmptyAudit({ onDemo, disabled }: { onDemo: () => Promise<void>; disabled: boolean }) {
  return <section className="empty-audit" aria-label="Getting started"><div className="empty-crosshair"><span /><span /><span /><span /><div><House size={27} strokeWidth={1.2} /></div></div><h2>A little clarity goes a long way.</h2><p>Start an audit to uncover what is holding your website back.<br />Get real evidence, practical fixes, and a place to decide what comes next.</p><div className="empty-steps"><span><b>01</b>Audit your pages</span><span><b>02</b>Understand the evidence</span><span><b>03</b>Choose your next move</span></div><button className="text-button" onClick={() => void onDemo()} disabled={disabled}>See how it works with a sample audit</button></section>;
}
