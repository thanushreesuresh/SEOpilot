import { ArrowUpRight, Check, CircleCheck, Navigation, Info, LoaderCircle } from "lucide-react";
import { useState } from "react";
export function Severity({ value }: { value: string }) { return <span className={`severity severity-${value.toLowerCase()}`}>{value}</span>; }
export function Status({ value }: { value: string }) { return <span className={`status status-${value}`}><span />{value.replaceAll("_", " ")}</span>; }
export function Brand() { return <div className="brand"><span className="brand-symbol"><Navigation size={19} strokeWidth={1} fill="currentColor" /></span><span>SEOPilot</span></div>; }
export function Spinner({ size = 18 }: { size?: number }) { return <LoaderCircle aria-hidden="true" size={size} className="spin" />; }
export function Notice({ children, variant = "info" }: { children: React.ReactNode; variant?: "info" | "error" | "success" }) { return <div className={`notice notice-${variant}`} role={variant === "error" ? "alert" : "status"}><Info size={18} aria-hidden="true" /><div>{children}</div></div>; }
export function Verified({ sample = false }: { sample?: boolean }) { return <span className="verified"><CircleCheck size={13} aria-hidden="true" />{sample ? "Sample finding" : "Verified finding"}</span>; }
export function ExternalUrl({ url, children }: { url: string; children: React.ReactNode }) {
  const safe = /^https?:\/\//i.test(url);
  return safe ? <a href={url} target="_blank" rel="noopener noreferrer" className="external-url">{children}<ArrowUpRight size={13} aria-hidden="true" /></a> : <span>{children}</span>;
}
export function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState(false);
  async function copy() { try { await navigator.clipboard.writeText(text); setCopied(true); setError(false); window.setTimeout(() => setCopied(false), 2000); } catch { setError(true); } }
  return <><button className="button button-small button-secondary" onClick={copy}>{copied ? <Check size={14} /> : <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><rect x="8" y="8" width="12" height="13" rx="2" /><path d="M15 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h3" /></svg>}{copied ? "Copied" : "Copy suggestion"}</button>{error ? <p role="alert" className="field-error">Clipboard unavailable. Select the suggestion text to copy it.</p> : null}</>;
}
