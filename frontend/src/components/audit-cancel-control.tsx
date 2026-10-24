import { useEffect, useRef, useState } from "react";
import { Square } from "lucide-react";
import { api, type Audit } from "@/lib/api";
import { Spinner } from "./ui";

export function AuditCancelControl({ auditId, onCancelled }: { auditId: string; onCancelled: (audit: Audit) => void }) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);

  async function cancel() {
    const abort = new AbortController();
    controller.current = abort;
    setPending(true); setError("");
    try {
      const audit = await api.cancel(auditId, abort.signal);
      if (!abort.signal.aborted) onCancelled(audit);
    } catch (cause) {
      if (!abort.signal.aborted) setError(cause instanceof Error ? cause.message : "Could not cancel this audit. Try again.");
    } finally {
      if (!abort.signal.aborted) setPending(false);
    }
  }

  return <div className="audit-cancel-control">
    <div><p>Stop this audit and keep the evidence collected so far.</p><p className="report-note">The admission and reserved AI calls remain charged. An AI request already in progress may still be billed.</p>{error ? <p className="field-error" role="alert">{error}</p> : null}</div>
    <button className="button button-small button-secondary" disabled={pending} onClick={() => void cancel()}>{pending ? <Spinner size={13} /> : <Square size={13} aria-hidden="true" />}{pending ? "Cancelling…" : "Cancel audit"}</button>
  </div>;
}
