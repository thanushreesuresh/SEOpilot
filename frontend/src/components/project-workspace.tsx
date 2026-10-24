"use client";

import { useCallback, useEffect, useState } from "react";
import { Check, Download, ExternalLink, FileDiff, GitPullRequest, Plus, RefreshCw, ShieldCheck, Trash2 } from "lucide-react";
import { api, dateTime, domain, pagePath, type Audit, type AuditSummary } from "@/lib/api";
import { fixApi, type ConnectionStatus, type FixRun, type PatchExport, type Project, type ProjectRequest } from "@/lib/fix-api";
import { Notice, Spinner } from "./ui";

const setupGuide = "https://github.com/thanushreesuresh/SEOpilot/blob/main/docs/github-app-setup.md";
const pollStatuses = new Set(["preparing", "publishing", "pr_opened", "checks_passed", "checks_failed", "merged"]);
const terminalStatuses = new Set(["live_verified", "cancelled", "expired", "conflict", "failed"]);
const message = (cause: unknown) => cause instanceof Error ? cause.message : "This action could not be completed. Please try again.";
const label = (value: string) => value.replaceAll("_", " ");

export function ProjectWorkspace({ history, currentAudit }: {history: AuditSummary[]; currentAudit: Audit | null}) {
  const [connection, setConnection] = useState<ConnectionStatus | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [onboarding, setOnboarding] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);
  const selected = projects.find((project) => project.id === selectedId);

  const refresh = useCallback(async (signal?: AbortSignal) => {
    const [status, items] = await Promise.all([fixApi.connection(signal), fixApi.projects(signal)]);
    if (signal?.aborted) return;
    setConnection(status); setProjects(items); setSelectedId((current) => items.some((item) => item.id === current) ? current : items[0]?.id ?? "");
  }, []);
  useEffect(() => {
    const abort = new AbortController();
    void Promise.all([fixApi.connection(abort.signal), fixApi.projects(abort.signal)]).then(([status, items]) => {
      if (!abort.signal.aborted) {setConnection(status); setProjects(items); setSelectedId((current) => items.some((item) => item.id === current) ? current : items[0]?.id ?? "");}
    }).catch((cause) => { if (!abort.signal.aborted) setError(message(cause)); }).finally(() => {if (!abort.signal.aborted) setLoading(false);});
    return () => abort.abort();
  }, []);

  async function created(project: Project) {
    setProjects((items) => [project, ...items.filter((item) => item.id !== project.id)]); setSelectedId(project.id); setOnboarding(false);
  }
  async function disconnect() {
    if (!selected) return;
    setDisconnecting(true); setError("");
    try { await fixApi.disconnect(selected.id); await refresh(); }
    catch (cause) {setError(message(cause));}
    finally {setDisconnecting(false);}
  }
  return <div className="project-workspace">
    <section className="page-heading history-heading"><div><h1>Review. Publish. Verify.</h1><p>Turn approved page metadata into a draft pull request.</p></div><button className="button button-secondary" onClick={() => {setError(""); void refresh().catch((cause) => setError(message(cause)));}}><RefreshCw size={15} />Refresh connection</button></section>
    {error ? <Notice variant="error">{error}</Notice> : null}
    {loading ? <div className="loading-surface" role="status"><Spinner />Loading projects…</div> : <>
      <section className="project-card connection-card" aria-label="GitHub App connection"><div className="project-section-heading"><div><span className="project-eyebrow">Repository connection</span><h2><ShieldCheck size={20} />{connection?.configured ? "GitHub App configured" : "Connect your GitHub App"}</h2></div><span className={`fix-status ${connection?.configured ? "fix-status-checks_passed" : ""}`}>{connection?.configured ? `${connection.repositories.length} repositories available` : "Setup required"}</span></div><p>{connection?.message ?? "Connection status is unavailable. Refresh to try again."}</p><p>Private source stays outside OpenAI requests. Patch generation uses reviewed text and makes zero additional AI calls.</p><div className="project-actions"><a className="button button-secondary" href={setupGuide} target="_blank" rel="noreferrer">Setup guide<ExternalLink size={13} /></a><button className="button button-primary" onClick={() => setOnboarding((value) => !value)} disabled={!connection?.configured || !connection.repositories.length}><Plus size={15} />{onboarding ? "Close project setup" : "Connect a project"}</button></div><p className="project-footnote">{connection?.actions_notice} {connection ? `${connection.publications_remaining} of ${connection.publication_limit} draft PR publications remain in the rolling 24-hour allowance.` : ""}</p></section>
      {onboarding && connection ? <ProjectOnboarding connection={connection} onCreated={created} /> : null}
      {projects.length ? <section className="project-card" aria-label="Connected projects"><div className="project-section-heading"><h2>Your projects</h2><label className="project-select">Project<select value={selectedId} onChange={(event) => setSelectedId(event.target.value)}>{projects.map((project) => <option key={project.id} value={project.id}>{project.name}{project.connected ? "" : " (disconnected)"}</option>)}</select></label></div>{selected ? <><div className="project-mapping"><div><span>Production website</span><a href={selected.production_origin} target="_blank" rel="noreferrer">{selected.production_origin}<ExternalLink size={12} /></a></div><div><span>Source repository</span><strong>{selected.repository_owner}/{selected.repository_name}</strong></div><div><span>Base branch · application</span><code>{selected.base_branch} · {selected.app_subdirectory || "/"}</code></div><div><span>Validation workflow</span><code>{selected.workflow}</code></div></div><details className="project-danger"><summary>Connection and source retention</summary><p>Source and patches expire after 24 hours. Disconnecting removes retained private source and prevents further publication. The installed GitHub App can also be removed in your GitHub settings.</p><button className="button button-secondary" disabled={!selected.connected || disconnecting} onClick={() => void disconnect()}>{disconnecting ? <Spinner size={14} /> : <Trash2 size={14} />}Disconnect and delete retained source</button></details></> : null}</section> : <div className="project-empty"><GitPullRequest size={27} /><h2>Your first reviewed change starts here.</h2><p>Connect an owned Next.js site, finish a live audit, then review a title or description patch before publishing.</p></div>}
      {selected ? <ProjectFixes key={selected.id} project={selected} history={history} currentAudit={currentAudit} onPublished={() => {void refresh().catch((cause) => setError(message(cause)));}} /> : null}
    </>}
  </div>;
}

function ProjectOnboarding({ connection, onCreated }: {connection: ConnectionStatus; onCreated: (project: Project) => Promise<void>}) {
  const [repositoryId, setRepositoryId] = useState(String(connection.repositories[0]?.id ?? ""));
  const repository = connection.repositories.find((item) => String(item.id) === repositoryId);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!repository) return;
    const form = new FormData(event.currentTarget);
    const data: ProjectRequest = {name: String(form.get("name") ?? ""), production_origin: String(form.get("origin") ?? ""), installation_id: repository.installation_id,
      repository_id: repository.id, base_branch: String(form.get("branch") ?? ""), app_subdirectory: String(form.get("subdirectory") ?? ""),
      workflow: String(form.get("workflow") ?? "seopilot-validation.yml"), confirms_ownership: true};
    setPending(true); setError("");
    try {await onCreated(await fixApi.createProject(data));} catch(cause) {setError(message(cause));} finally {setPending(false);}
  }
  return <section className="project-card" aria-labelledby="project-setup-heading"><span className="project-eyebrow">01 · Map a website to its source</span><h2 id="project-setup-heading">Connect an owned Next.js project</h2><form className="project-form" onSubmit={(event) => void submit(event)}><div className="project-form-grid"><label>Project name<input name="name" required maxLength={100} placeholder="My website" /></label><label>Production origin<input name="origin" type="url" required placeholder="https://your-website.com" /></label><label>Installed repository<select value={repositoryId} onChange={(event) => setRepositoryId(event.target.value)}>{connection.repositories.map((item) => <option key={item.id} value={item.id}>{item.owner}/{item.name}</option>)}</select></label><label key={repositoryId}>Base branch<input name="branch" required maxLength={200} defaultValue={repository?.default_branch ?? "main"} /></label><label>Application subdirectory<input name="subdirectory" maxLength={200} placeholder="Blank for repository root" /></label><label>Owner-installed workflow filename<input name="workflow" required defaultValue="seopilot-validation.yml" pattern="[A-Za-z0-9_-]+\.ya?ml" /></label></div><label className="project-consent"><input name="ownership" type="checkbox" required /><span>I own this website and confirm that this repository and application directory supply its production code.</span></label><p className="project-footnote">Install the validation workflow from the setup guide yourself. Publishing a branch or draft PR may run CI or preview builds, which can incur GitHub Actions usage.</p>{error ? <Notice variant="error">{error}</Notice> : null}<button className="button button-primary" disabled={pending}>{pending ? <Spinner size={14} /> : <Check size={14} />}Confirm project mapping</button></form></section>;
}

function ProjectFixes({ project, history, currentAudit, onPublished }: {project: Project; history: AuditSummary[]; currentAudit: Audit | null; onPublished: () => void}) {
  const [runs, setRuns] = useState<FixRun[]>([]);
  const [selected, setSelected] = useState<FixRun | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const refresh = useCallback(async (signal?: AbortSignal) => {
    const items = await fixApi.runs(project.id, signal);
    if (!signal?.aborted) {setRuns(items); setSelected((current) => current ? items.find((item) => item.id === current.id) ?? current : items[0] ?? null);}
  }, [project.id]);
  useEffect(() => {
    const abort = new AbortController();
    void fixApi.runs(project.id, abort.signal).then((items) => {
      if (!abort.signal.aborted) {setRuns(items); setSelected((current) => current ? items.find((item) => item.id === current.id) ?? current : items[0] ?? null);}
    }).catch((cause) => {if (!abort.signal.aborted) setError(message(cause));}).finally(() => {if (!abort.signal.aborted) setLoading(false);});
    return () => abort.abort();
  }, [project.id, project.connected]);
  function update(run: FixRun) {setSelected(run); setRuns((items) => [run, ...items.filter((item) => item.id !== run.id)]);}
  const active = runs.some((run) => !terminalStatuses.has(run.status));
  return <>
    {project.connected ? <ProposalForm project={project} history={history} currentAudit={currentAudit} disabled={active} onCreated={update} /> : <Notice>This project is disconnected. Its history remains available; connect the website again to prepare new changes.</Notice>}
    <section className="project-card" aria-label="Fix run history"><div className="project-section-heading"><div><span className="project-eyebrow">Your review record</span><h2>Fix run history</h2></div><button className="button button-small button-secondary" onClick={() => {setError(""); void refresh().catch((cause) => setError(message(cause)));}}><RefreshCw size={13} />Refresh</button></div>{error ? <Notice variant="error">{error}</Notice> : null}{loading ? <p role="status"><Spinner size={14} />Loading fix runs…</p> : runs.length ? <div className="fix-history">{runs.map((run) => <button key={run.id} className={`fix-history-item ${selected?.id === run.id ? "selected" : ""}`} aria-pressed={selected?.id === run.id} onClick={() => setSelected(run)}><span><strong>{run.targets.length} {run.targets.length === 1 ? "page" : "pages"} · {run.changed_files.length} files</strong><small>{dateTime(run.created_at)}</small></span><span className={`fix-status fix-status-${run.status}`}>{label(run.status)}</span></button>)}</div> : <p className="project-muted">No proposals yet. Prepared patches and subsequent checks appear here.</p>}</section>
    {selected ? <FixDetails key={`${selected.id}-${selected.source_purged}-${project.connected}`} run={selected} connected={project.connected} onUpdate={update} onPublished={onPublished} /> : null}
  </>;
}

type EditRow = {url: string; selected: boolean; title: string; description: string; titleId?: string; descriptionId?: string};
function initialEdits(audit: Audit): EditRow[] {
  return audit.pages.filter((page, index, pages) => page.outcome === "html" && pages.findIndex((other) => other.url === page.url) === index).map((page) => {
    const title = audit.recommendations.find((item) => item.url === page.url && item.kind === "title" && item.status === "approved" && item.suggested_value);
    const description = audit.recommendations.find((item) => item.url === page.url && item.kind === "description" && item.status === "approved" && item.suggested_value);
    return {url: page.url, selected: false, title: title?.suggested_value ?? "", description: description?.suggested_value ?? "", titleId: title?.id, descriptionId: description?.id};
  });
}

function ProposalForm({project, history, currentAudit, disabled, onCreated}: {project: Project; history: AuditSummary[]; currentAudit: Audit | null; disabled: boolean; onCreated: (run: FixRun) => void}) {
  const eligible = history.filter((item) => item.mode === "live" && ["completed", "partial"].includes(item.status) && new URL(item.url).origin === project.production_origin);
  const usableCurrent = currentAudit?.mode === "live" && ["completed", "partial"].includes(currentAudit.status) && currentAudit.origin === project.production_origin ? currentAudit : null;
  const [audit, setAudit] = useState<Audit | null>(usableCurrent);
  const [edits, setEdits] = useState<EditRow[]>(() => usableCurrent ? initialEdits(usableCurrent) : []);
  const [pending, setPending] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const selectedCount = edits.filter((row) => row.selected).length;
  async function selectAudit(id: string) {
    setError(""); setAudit(null); setEdits([]); if (!id) return;
    setLoading(true);
    try {const next = await api.audit(id); setAudit(next); setEdits(initialEdits(next));} catch(cause) {setError(message(cause));} finally {setLoading(false);}
  }
  function change(url: string, field: "title" | "description", value: string) {setEdits((items) => items.map((item) => item.url === url ? {...item, [field]: value, [field === "title" ? "titleId" : "descriptionId"]: undefined} : item));}
  async function create(event: React.FormEvent) {
    event.preventDefault(); if (!audit) return;
    const chosen = edits.filter((row) => row.selected);
    if (!chosen.length || chosen.some((row) => !row.title.trim() && !row.description.trim())) {setError("Select one to three pages and enter a title or description for each."); return;}
    setPending(true); setError("");
    try {onCreated(await fixApi.create({project_id: project.id, audit_id: audit.id, edits: chosen.map((row) => ({url: row.url,
      ...(row.title.trim() ? {title: row.title} : {}), ...(row.description.trim() ? {description: row.description} : {}),
      recommendation_ids: [row.titleId, row.descriptionId].filter((value): value is string => Boolean(value))}))}));}
    catch(cause) {setError(message(cause));} finally {setPending(false);}
  }
  return <section className="project-card" aria-labelledby="prepare-patch-heading"><span className="project-eyebrow">02 · Prepare a private patch</span><h2 id="prepare-patch-heading">Choose reviewed metadata changes</h2><p>Only static App Router server pages are supported. Titles and descriptions can use approved suggestions or text you enter. Blank fields stay unchanged.</p>{disabled ? <Notice>One active fix run is allowed per project. Complete or cancel the current run before preparing another.</Notice> : null}<form className="project-form" onSubmit={(event) => void create(event)}><label className="project-select">Completed live audit<select value={audit?.id ?? ""} onChange={(event) => void selectAudit(event.target.value)} disabled={disabled || pending || loading}><option value="">Select an audit for {domain(project.production_origin)}</option>{eligible.map((item) => <option key={item.id} value={item.id}>{dateTime(item.created_at)} · {item.pages} pages · {item.status}</option>)}</select></label>{!eligible.length ? <p className="project-muted">Run a live audit of this production website first. Sample audits cannot create source patches.</p> : null}{loading ? <p role="status"><Spinner size={14} />Loading page evidence…</p> : null}{edits.length ? <><p className="project-footnote">{selectedCount} of 3 pages selected. Approved text is prefilled; other fields wait for your input. No source is sent to AI.</p><div className="metadata-edits">{edits.map((row, index) => <fieldset key={row.url} disabled={disabled || pending}><legend><label className="project-consent"><input type="checkbox" checked={row.selected} disabled={!row.selected && selectedCount >= 3} onChange={(event) => setEdits((items) => items.map((item) => item.url === row.url ? {...item, selected: event.target.checked} : item))} /><span>{pagePath(row.url)}</span></label></legend><a href={row.url} target="_blank" rel="noreferrer" className="project-muted">{row.url}</a><div className="project-form-grid"><label htmlFor={`metadata-title-${index}`}>Page title {row.titleId ? <small>Approved suggestion</small> : null}<input id={`metadata-title-${index}`} value={row.title} onChange={(event) => change(row.url, "title", event.target.value)} maxLength={120} placeholder="Enter a title or leave unchanged" disabled={!row.selected} /></label><label htmlFor={`metadata-description-${index}`}>Meta description {row.descriptionId ? <small>Approved suggestion</small> : null}<textarea id={`metadata-description-${index}`} value={row.description} onChange={(event) => change(row.url, "description", event.target.value)} maxLength={320} placeholder="Enter a description or leave unchanged" disabled={!row.selected} rows={3} /></label></div></fieldset>)}</div></> : null}{error ? <Notice variant="error">{error}</Notice> : null}<button className="button button-primary" disabled={disabled || pending || loading || !selectedCount}>{pending ? <Spinner size={14} /> : <FileDiff size={15} />}Prepare patch for review</button><p className="project-footnote">Preparing a patch does not publish a branch or PR. Maximum: 3 pages, 5 files, 100 changed lines. Dynamic routes and metadata need manual changes.</p></form></section>;
}

function FixDetails({run, connected, onUpdate, onPublished}: {run: FixRun; connected: boolean; onUpdate: (run: FixRun) => void; onPublished: () => void}) {
  const [patch, setPatch] = useState<PatchExport | null>(null);
  const [consent, setConsent] = useState(false);
  const [deployed, setDeployed] = useState(false);
  const [pending, setPending] = useState("");
  const [error, setError] = useState("");
  const [pollNotice, setPollNotice] = useState("");
  const pollable = pollStatuses.has(run.status) || (run.status === "awaiting_deployment" && Boolean(run.verification_audit_id));
  useEffect(() => {
    if (!pollable) return;
    const abort = new AbortController();
    const started = Date.now();
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      if (Date.now() - started >= 10 * 60 * 1000) {setPollNotice("Automatic status checks paused after ten minutes. Refresh when you are ready."); return;}
      try {const next = await fixApi.run(run.id, abort.signal); if (abort.signal.aborted) return; onUpdate(next); if (pollStatuses.has(next.status) || (next.status === "awaiting_deployment" && next.verification_audit_id)) timer = setTimeout(poll, 5000);}
      catch(cause) {if (!abort.signal.aborted) setPollNotice(`Automatic status checks paused: ${message(cause)} Use Refresh status to retry.`);}
    }
    timer = setTimeout(poll, 5000);
    return () => {abort.abort(); clearTimeout(timer);};
    // The poll owns the lifecycle for this selected run; callback identity must not restart its ten-minute bound.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [run.id, pollable]);
  async function action(name: string, execute: () => Promise<FixRun>) {
    setPending(name); setError("");
    try {const next = await execute(); onUpdate(next); if (name === "publish") {setConsent(false); onPublished();} if (name === "delete") {setPatch(null); setConsent(false);}}
    catch(cause) {setError(message(cause));} finally {setPending("");}
  }
  async function loadPatch() {
    setPending("patch"); setError(""); setConsent(false);
    try {const next = await fixApi.patch(run.id); if (next.patch_hash !== run.patch_hash) throw new Error("This patch no longer matches the proposal. Refresh status before proceeding."); setPatch(next);}
    catch(cause) {setError(message(cause));} finally {setPending("");}
  }
  function download() {
    if (!patch) return;
    const url = URL.createObjectURL(new Blob([patch.patch], {type: "text/x-diff;charset=utf-8"}));
    const link = document.createElement("a"); link.href = url; link.download = patch.filename; link.click(); URL.revokeObjectURL(url);
  }
  const canPublish = connected && run.status === "proposed" && !run.source_purged && patch?.patch_hash === run.patch_hash;
  const canVerify = connected && ["awaiting_deployment", "verification_failed"].includes(run.status);
  return <section className="project-card fix-details" aria-labelledby="fix-review-heading"><div className="project-section-heading"><div><span className="project-eyebrow">03 · Review, publish, verify</span><h2 id="fix-review-heading">Proposed metadata changes</h2></div><span className={`fix-status fix-status-${run.status}`}>{label(run.status)}</span></div><p role="status">{run.message}</p><ol className="fix-lifecycle" aria-label="Delivery stages">{[["pr_opened", "Draft PR"], ["checks_passed", "Checks passed"], ["merged", "Merged"], ["awaiting_deployment", "Awaiting deployment"], ["live_verified", "Live verified"]].map(([state, text]) => <li key={state} aria-current={run.status === state ? "step" : undefined} className={run.status === state ? "current" : ""}>{text}</li>)}</ol><div className="project-actions"><button className="button button-secondary" disabled={!!pending} onClick={() => {setPollNotice(""); void action("refresh", () => fixApi.refresh(run.id));}}><RefreshCw size={14} />Refresh status</button>{run.pr_url ? <a className="button button-primary" href={run.pr_url} target="_blank" rel="noreferrer">Open pull request<ExternalLink size={14} /></a> : null}{!run.source_purged ? <button className="button button-secondary" disabled={!!pending || !connected || !run.patch_hash} onClick={() => void loadPatch()}><FileDiff size={14} />{pending === "patch" ? "Loading diff…" : "Inspect exact diff"}</button> : null}{patch ? <button className="button button-secondary" onClick={download}><Download size={14} />Download patch</button> : null}</div>{pollNotice ? <Notice>{pollNotice}</Notice> : null}{error ? <Notice variant="error">{error}</Notice> : null}<div className="project-mapping"><div><span>Base commit</span><code>{run.base_sha}</code></div><div><span>Patch SHA-256</span><code>{run.patch_hash}</code></div><div><span>Scope</span><strong>{run.targets.length} pages · {run.changed_files.length} files · {run.changed_lines} changed lines</strong></div><div><span>Private source expires</span><strong>{dateTime(run.expires_at)}</strong></div></div><div className="fix-targets">{run.targets.map((target) => <article key={target.url}><h3>{pagePath(target.url)}</h3><code>{target.path}</code><dl><div><dt>Title</dt><dd><del>{target.old_title ?? "(not set)"}</del><span>{target.title ?? "(unchanged / not set)"}</span></dd></div><div><dt>Description</dt><dd><del>{target.old_description ?? "(not set)"}</del><span>{target.description ?? "(unchanged / not set)"}</span></dd></div></dl></article>)}</div>{patch ? <div className="patch-review"><h3>Exact proposed diff</h3><p>Read all changes before approving publication. Code below is displayed as escaped text.</p><pre tabIndex={0} aria-label="Proposed code diff"><code>{patch.patch}</code></pre></div> : run.source_purged ? <Notice>Retained source and patches were deleted. Historical metadata, hashes and results remain available.</Notice> : <p className="project-muted">Inspect the complete diff to unlock publication. Downloading the patch is also available without creating a branch.</p>}{run.status === "proposed" ? <div className="publication-consent"><label className="project-consent"><input type="checkbox" checked={consent} disabled={!canPublish || !!pending} onChange={(event) => setConsent(event.target.checked)} /><span>I reviewed this exact patch and approve creating its draft PR. I understand repository CI and preview automation may run and use GitHub Actions allowance.</span></label><button className="button button-primary" disabled={!canPublish || !consent || !!pending} onClick={() => {if (patch) void action("publish", () => fixApi.publish(run.id, patch.patch_hash));}}>{pending === "publish" ? <Spinner size={14} /> : <GitPullRequest size={15} />}Create draft PR</button><p className="project-footnote">Recommendation approval is content review. Only this separate action authorizes a GitHub write. Merging and deployment stay under your control.</p></div> : null}<section className="validation-summary" aria-label="Validation results"><h3>GitHub-hosted validation · {label(run.validation.status)}</h3><p>{run.validation.summary}</p>{run.validation.run_url ? <a href={run.validation.run_url} target="_blank" rel="noreferrer">Open validation run<ExternalLink size={13} /></a> : null}{Object.keys(run.validation.details).length ? <details><summary>Validation report</summary><pre>{JSON.stringify(run.validation.details, null, 2)}</pre></details> : null}<p className="project-footnote">CI runs on GitHub-hosted runners. OpenAI and GitHub App credentials stay on this machine. Missing or failed checks remain visible.</p></section>{canVerify ? <section className="verification-action"><h3>Verify the actual deployment</h3><p>A merged PR does not confirm that production changed. Verification audits the recorded URLs with AI disabled and uses the existing daily audit allowance.</p><label className="project-consent"><input type="checkbox" checked={deployed} onChange={(event) => setDeployed(event.target.checked)} /><span>I deployed the merged change to the recorded production website.</span></label><button className="button button-primary" disabled={!deployed || !!pending} onClick={() => void action("verify", () => fixApi.verify(run.id))}>{pending === "verify" ? <Spinner size={14} /> : <ShieldCheck size={15} />}Verify live</button></section> : null}{Object.keys(run.verification).length ? <section className="validation-summary" aria-label="Live verification results"><h3>Live verification</h3><pre>{JSON.stringify(run.verification, null, 2)}</pre><p className="project-footnote">Blocked, failed and unchecked pages remain unresolved. Reduced coverage never becomes a clean verification.</p></section> : null}<details className="project-danger"><summary>Cancel or delete private source</summary><p>Cancellation prevents new work. Deleting source immediately removes retained source and the downloadable patch; published GitHub branches and PRs remain on GitHub.</p><div className="project-actions"><button className="button button-secondary" disabled={!!pending || terminalStatuses.has(run.status)} onClick={() => void action("cancel", () => fixApi.cancel(run.id))}>Cancel fix run</button><button className="button button-secondary" disabled={!!pending || run.source_purged} onClick={() => void action("delete", () => fixApi.deleteSource(run.id))}><Trash2 size={14} />Delete retained source now</button></div></details></section>;
}
