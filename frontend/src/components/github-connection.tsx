"use client";

import { ExternalLink, Plus, ShieldCheck } from "lucide-react";
import { dateTime } from "@/lib/api";
import type { ConnectionStatus } from "@/lib/fix-api";

const setupGuide = "https://github.com/thanushreesuresh/SEOpilot/blob/main/docs/github-app-setup.md";
const states: Record<ConnectionStatus["state"], string> = {
  unknown: "Not verified", setup_required: "Setup required", invalid_settings: "Settings need correction", ready: "Repositories verified",
  no_repositories: "No repositories available", credentials_error: "Authentication failed",
  access_denied: "Access not verified", rate_limited: "GitHub rate limit", unavailable: "Verification unavailable",
};

export function GitHubConnection({ connection, checking, onboarding, onConnect }: {
  connection: ConnectionStatus | null; checking: boolean; onboarding: boolean; onConnect: () => void;
}) {
  const ready = connection?.state === "ready" && connection.configured && connection.repositories.length > 0;
  const failed = connection && ["invalid_settings", "credentials_error", "access_denied", "rate_limited", "unavailable"].includes(connection.state);
  const heading = checking ? "Checking GitHub connection" : !connection ? "Connection status unavailable"
    : connection.state === "invalid_settings" ? "GitHub settings need correction"
    : ready ? "GitHub connection verified" : connection.configured ? "GitHub connection needs attention" : "Connect your GitHub App";
  return <section className="project-card connection-card" aria-label="GitHub App connection" aria-busy={checking}>
    <div className="project-section-heading">
      <div><span className="project-eyebrow">Repository connection</span><h2><ShieldCheck size={20} />{heading}</h2></div>
      <span className={`fix-status ${ready ? "fix-status-checks_passed" : ""}`}>
        {checking ? "Checking…" : connection ? ready ? `${connection.repositories.length} repositories verified` : states[connection.state] ?? "Not verified" : "Not verified"}
      </span>
    </div>
    <p role={failed ? "alert" : "status"}>{checking ? "Checking local configuration and selected repositories…" : connection?.message ?? "Connection status is unavailable. Refresh to try again."}</p>
    {connection?.setup_checks?.length ? <div className="connection-diagnostics">
      <h3>Server-side App settings</h3>
      <ul aria-label="Server-side App settings">{connection.setup_checks.map((check) => <li key={check.setting}>
        <code>{check.setting}</code><span>{check.present ? "Present" : "Missing"}</span>
      </li>)}</ul>
      <p>Only setting presence is shown. Values and key contents stay on the server. Presence alone does not validate credentials; configuration changes require a backend restart.</p>
    </div> : null}
    {connection?.checked_at ? <p className="connection-checked">Last checked {dateTime(connection.checked_at)}</p> : null}
    <p>Private source stays outside OpenAI requests. Patch generation uses reviewed text and makes zero additional AI calls.</p>
    <div className="project-actions">
      <a className="button button-secondary" href={setupGuide} target="_blank" rel="noreferrer">Setup guide<ExternalLink size={13} /></a>
      <button className="button button-primary" onClick={onConnect} disabled={!ready || checking}>
        <Plus size={15} />{onboarding ? "Close project setup" : "Connect a project"}
      </button>
    </div>
    <p className="project-footnote">{connection?.actions_notice} {connection ? `${connection.publications_remaining} of ${connection.publication_limit} draft PR publications remain in the rolling 24-hour allowance.` : ""}</p>
  </section>;
}
