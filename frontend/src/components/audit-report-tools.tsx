import { useEffect, useRef, useState } from "react";
import { Download } from "lucide-react";
import { reportingApi, type ReportFormat } from "@/lib/reporting-api";
import { Spinner } from "./ui";

export function AuditReportTools({ auditId, active }: { auditId: string; active: boolean }) {
  const [format, setFormat] = useState<ReportFormat>("markdown");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [prepared, setPrepared] = useState("");
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);

  async function download() {
    controller.current?.abort();
    const abort = new AbortController();
    controller.current = abort;
    setPending(true); setError(""); setPrepared("");
    try {
      const report = await reportingApi.report(auditId, format, abort.signal);
      if (abort.signal.aborted) return;
      const blobUrl = URL.createObjectURL(new Blob([report.content], { type: report.media_type }));
      const link = document.createElement("a");
      const filename = report.filename.split(/[\\/]/).pop() || `seopilot-report.${format === "markdown" ? "md" : format}`;
      link.href = blobUrl; link.download = filename;
      document.body.append(link); link.click(); link.remove();
      window.setTimeout(() => URL.revokeObjectURL(blobUrl), 1000);
      setPrepared(`Report prepared: ${filename}`);
    } catch (cause) {
      if (!abort.signal.aborted) setError(cause instanceof Error ? cause.message : "Could not download the report. Please try again.");
    } finally {
      if (!abort.signal.aborted) setPending(false);
    }
  }

  return <div className="audit-report-tools" aria-label="Audit report export">
    <div className="audit-report-controls">
      <label className="sr-only" htmlFor={`report-format-${auditId}`}>Report format</label>
      <select id={`report-format-${auditId}`} value={format} onChange={(event) => { setFormat(event.target.value as ReportFormat); setPrepared(""); setError(""); }} disabled={active || pending}>
        <option value="markdown">Markdown</option><option value="csv">CSV</option><option value="json">JSON</option>
      </select>
      <button className="button button-small button-secondary" onClick={() => void download()} disabled={active || pending}>{pending ? <Spinner size={14} /> : <Download size={14} aria-hidden="true" />}{pending ? "Preparing report…" : "Download report"}</button>
    </div>
    <p className="report-note">{active ? "Reports are available when this audit finishes." : "Export saved results. No new crawl or AI calls."}</p>
    {error ? <p className="field-error" role="alert">{error}</p> : null}
    {prepared ? <p className="report-note" role="status">{prepared}</p> : null}
  </div>;
}
