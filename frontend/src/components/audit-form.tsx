import { useState, type FormEvent } from "react";
import { ArrowRight, ChevronDown, Link2, SlidersHorizontal } from "lucide-react";
import { Spinner } from "./ui";
type Props = { onSubmit: (url: string, context: string, limit: number, depth: number) => Promise<void>; onDemo: () => Promise<void>; submitting: "live" | "demo" | null; active: boolean; initializing: boolean };
export function AuditForm({ onSubmit, onDemo, submitting, active, initializing }: Props) {
  const [url, setUrl] = useState("");
  const [context, setContext] = useState("");
  const [showContext, setShowContext] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [pageLimit, setPageLimit] = useState(15);
  const [depth, setDepth] = useState(2);
  const disabled = !!submitting || active || initializing;
  function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); void onSubmit(url.trim(), context.trim(), pageLimit, depth); }
  return <section className="audit-form-panel" aria-labelledby="audit-form-heading"><form onSubmit={submit}>
    <div className="form-heading"><h2 id="audit-form-heading">Start with your website</h2><button className="settings-toggle" type="button" onClick={() => setShowSettings(!showSettings)} aria-expanded={showSettings} aria-controls="crawl-settings"><SlidersHorizontal size={14} />Crawl settings<ChevronDown className={showSettings ? "rotated" : ""} size={13} /></button></div>
    <div className="audit-form-row"><div className="url-field"><Link2 size={19} aria-hidden="true" /><label className="sr-only" htmlFor="website-url">Website URL</label><input id="website-url" type="url" inputMode="url" placeholder="https://yourwebsite.com" value={url} onChange={(event) => setUrl(event.target.value)} required maxLength={2048} autoComplete="url" disabled={!!submitting || initializing} /></div><button className="button button-primary run-button" type="submit" disabled={disabled}>{submitting === "live" ? <Spinner size={16} /> : null}{active ? "Audit in progress" : submitting === "live" ? "Starting audit" : "Run audit"}{!disabled ? <ArrowRight size={17} /> : null}</button><button type="button" className={`button button-secondary context-button ${showContext ? "toggled" : ""}`} onClick={() => setShowContext(!showContext)} aria-expanded={showContext} aria-controls="business-context"><SlidersHorizontal size={15} />{showContext ? "Hide business context" : "Add business context"}</button><button className="button button-secondary demo-button" type="button" onClick={() => void onDemo()} disabled={!!submitting || initializing}>{submitting === "demo" ? <Spinner size={16} /> : null}Explore sample audit</button></div>
    {showContext ? <div className="context-field"><label htmlFor="business-context">Business context <span>optional</span></label><textarea id="business-context" value={context} onChange={(event) => setContext(event.target.value)} maxLength={2000} rows={3} placeholder="What does your business do, and who would you like to reach?" /><p>Helps optional AI suggestions fit your audience. {context.length}/2,000 characters.</p></div> : null}
    {showSettings ? <div id="crawl-settings" className="crawl-settings"><div><label htmlFor="page-limit">Maximum pages</label><select id="page-limit" value={pageLimit} onChange={(event) => setPageLimit(Number(event.target.value))}>{[5, 10, 15, 20, 30].map((count) => <option value={count} key={count}>{count} pages</option>)}</select></div><div><label htmlFor="max-depth">Link depth</label><select id="max-depth" value={depth} onChange={(event) => setDepth(Number(event.target.value))}>{[0, 1, 2, 3].map((value) => <option key={value} value={value}>{value === 0 ? "Starting page only" : `${value} ${value === 1 ? "level" : "levels"}`}</option>)}</select></div><p>Same-origin pages only. Respects robots.txt, with at least 750 ms between requests.</p></div> : null}
    <p className="form-note">Read-only crawling. Every recommendation stays in your hands.</p>
  </form></section>;
}
