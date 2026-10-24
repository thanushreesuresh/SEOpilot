import type { Audit } from "@/lib/api";
import { ExternalUrl } from "./ui";

export function CrawlDiscoveryDetails({ audit }: { audit: Audit }) {
  const discovery = audit.discovery;
  return <section className="discovery-panel" aria-label="Crawl discovery">
    <h3>Robots and sitemap checks</h3>
    {!discovery ? <p>Discovery checks were not recorded for this audit; their outcomes remain unknown.</p> : <>
      <p>Robots policy: <strong>{discovery.robots_state}</strong> · Sitemap: <strong>{discovery.sitemap_state}</strong></p>
      <details>
        <summary>Inspect crawl discovery evidence</summary>
        <p>{audit.mode === "demo" ? "Sample fixture checks; no HTTP requests were made." : `${discovery.request_attempts} budgeted request attempts at the last saved update, including redirects and retries. Attempts may fail before an HTTP connection; interrupted runs may have later unrecorded attempts.`}</p>
        {audit.mode !== "demo" ? <p>Effective minimum delay: {discovery.effective_delay_seconds} seconds. Robots restrictions and the crawl time budget still apply.</p> : null}
        <ul className="discovery-probes">{discovery.probes.map((probe, index) => <li key={`${probe.kind}-${index}`}>
          <p><strong>{probe.kind === "robots" ? "Robots policy" : "Sitemap"}: {probe.outcome}</strong> · {probe.status_code === null ? "HTTP status not recorded" : `HTTP ${probe.status_code}`}</p>
          <ExternalUrl url={probe.url}>{probe.url}</ExternalUrl>
          <p>{probe.explanation}</p>
        </li>)}</ul>
        {!discovery.probes.length ? <p>No completed discovery checks were retained.</p> : null}
        {discovery.notes.length ? <ul>{discovery.notes.map((note, index) => <li key={index}>{note}</li>)}</ul> : null}
        <p>Up to three same-origin sitemap locations are inspected, stopping at the first recognized XML root. Other locations may exist. Listed sitemap URLs and search-engine indexing were not verified.</p>
        <p>Unknown means permission or presence could not be established. An absent file is not a ranking penalty. No additional requests or AI calls are made to display these saved checks.</p>
      </details>
    </>}
  </section>;
}
