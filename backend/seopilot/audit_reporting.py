"""Offline, bounded comparisons and reports from public audit evidence only."""

import csv
import hashlib
import html
import io
import json
import re
from collections import defaultdict
from typing import Any

from .models import Audit, Issue, Page
from .network import normalize_url, origin_of

MAX_REPORT_BYTES = 1024 * 1024
FINISHED_STATUSES = {"completed", "partial", "failed", "interrupted", "cancelled"}
CHANGE_STATUSES = ("added", "persistent", "resolved", "unresolved_unknown")
FindingKey = tuple[str, str, str, bool]


def _bounded(content: str) -> str:
    if len(content.encode("utf-8")) > MAX_REPORT_BYTES:
        raise ValueError("The report exceeds the 1 MiB output limit; narrow the audit scope and try again.")
    return content


def _json(value: Any, *, pretty: bool = False) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2 if pretty else None, sort_keys=False)


def _assessed(page: Page) -> bool:
    return page.status_code is not None and (
        page.outcome == "html" and 200 <= page.status_code < 300
        or page.outcome == "http_error" and 400 <= page.status_code < 600
    )


def _pages(audit: Audit, origin: str) -> dict[str, list[Page]]:
    indexed: dict[str, list[Page]] = defaultdict(list)
    for page in audit.pages:
        url = normalize_url(page.url)
        if origin_of(url) == origin:
            indexed[url].append(page)
    return dict(indexed)


def _assessed_urls(indexed: dict[str, list[Page]]) -> set[str]:
    return {url for url, pages in indexed.items() if any(_assessed(page) for page in pages)}


def _state(url: str, indexed: dict[str, list[Page]]) -> str:
    pages = indexed.get(url, [])
    if not pages:
        return "unchecked"
    if all(_assessed(page) for page in pages):
        return "assessed"
    if any(page.outcome == "blocked" for page in pages):
        return "blocked"
    if all(page.outcome == "non_html" for page in pages):
        return "unchecked"
    return "unknown"


def _key(issue: Issue) -> FindingKey:
    # The primary evidence field is emitted by the rule, unlike random persisted IDs.
    field = issue.evidence[0].field if issue.evidence else ""
    return issue.rule_id, normalize_url(issue.url), field, issue.is_site


def _findings(audit: Audit) -> dict[FindingKey, list[Issue]]:
    indexed: dict[FindingKey, list[Issue]] = defaultdict(list)
    pages_by_id = {page.id: page for page in audit.pages}
    for issue in audit.issues:
        key = _key(issue)
        urls = {key[1]}
        if not issue.is_site and len(issue.page_ids) > 1:
            # Group representatives depend on crawl order. Give every affected
            # URL its own stable observation while retaining the original group evidence.
            urls.update(normalize_url(pages_by_id[page_id].url) for page_id in issue.page_ids if page_id in pages_by_id)
        for url in sorted(urls):
            indexed[(key[0], url, key[2], key[3])].append(issue)
    return dict(indexed)


def _change(
    key: FindingKey, before: list[Issue], after: list[Issue], status: str, reason: str, after_state: str,
) -> dict[str, Any]:
    representative = min(after or before, key=lambda issue: (issue.title, issue.severity, issue.id))
    return {
        "stable_id": hashlib.sha256(_json(key).encode("utf-8")).hexdigest()[:24],
        "rule_id": key[0], "url": key[1], "field": key[2], "is_site": key[3],
        "title": representative.title, "severity": representative.severity, "status": status,
        "before_issue_ids": sorted({issue.id for issue in before}),
        "after_issue_ids": sorted({issue.id for issue in after}), "reason": reason, "after_state": after_state,
    }


def _evidence_field(issue: Issue) -> str | None:
    rule = issue.rule_id
    if rule.startswith("json_ld_"):
        return "structured_data"
    if rule.startswith("title_"):
        return "title"
    if rule.startswith("description_"):
        return "description"
    if rule.startswith(("h1_", "heading_")):
        return "headings"
    if rule.startswith("canonical_"):
        return "canonicals"
    if rule == "image_alt_missing":
        return "images"
    if rule == "indexing_restricted":
        return "robots"
    if rule == "broken_internal_link":
        return "links"
    if rule == "http_error":
        return "status_code"
    if rule == "non_https":
        return "url"
    field = issue.evidence[0].field if issue.evidence else ""
    return {"canonical": "canonicals", "h1_count": "headings"}.get(field, field) or None


def _resolution_unknown_reason(
    issues: list[Issue], before: Audit, after_index: dict[str, list[Page]], common: set[str], rules_match: bool,
    *, target: Audit,
) -> str | None:
    if not rules_match:
        return "Rule versions differ; absence under a different rule set does not prove resolution."
    if target.status not in {"completed", "partial"}:
        return "The later audit did not confirm deterministic analysis finished; missing findings remain unknown."
    if any(issue.is_site for issue in issues):
        before_urls = _assessed_urls(_pages(before, origin_of(before.origin or before.url)))
        if not common or before_urls != _assessed_urls(after_index):
            return "Site-policy findings require the same nonempty assessed URL scope in both audits."
        discovery = target.discovery
        for issue in issues:
            kind = {"robots_absent": "robots", "sitemap_absent": "sitemap"}.get(issue.rule_id)
            if discovery is None or kind is None or getattr(discovery, f"{kind}_state") != "present":
                return "The later audit does not retain an explicit successful site-policy inspection; absence is unknown."
            try:
                successful = any(
                    probe.kind == kind and probe.outcome == "present"
                    and probe.status_code is not None and 200 <= probe.status_code < 300
                    and origin_of(probe.url) == origin_of(target.origin or target.url)
                    for probe in discovery.probes
                )
            except ValueError:
                successful = False
            if not successful:
                return "The later audit has no matching successful same-origin policy probe; evidence is unknown."
        return None
    before_by_id = {page.id: page for page in before.pages}
    for issue in issues:
        urls = {normalize_url(issue.url)}
        for page_id in issue.page_ids:
            affected = before_by_id.get(page_id)
            if affected is None:
                return "A finding refers to page evidence unavailable in the earlier audit."
            urls.add(normalize_url(affected.url))
        field = _evidence_field(issue)
        for url in sorted(urls):
            if url not in common or _state(url, after_index) != "assessed":
                return "An affected URL is blocked, unchecked, or unknown in the common assessed scope."
            for page in after_index[url]:
                if field not in {"status_code", "url"} and page.outcome != "html":
                    return "An HTTP error response cannot verify a previous HTML finding was resolved."
                if field is None or not hasattr(page, field) or getattr(page, field) is None:
                    return "The later audit does not retain the required diagnostic field; evidence is unknown."
                if "body" in page.truncated_fields or field in page.truncated_fields:
                    return "The later evidence for an affected URL or field was truncated."
                if field == "structured_data" and page.structured_data.truncated:
                    return "The later structured-data diagnostic evidence was truncated."
        if issue.rule_id == "broken_internal_link":
            source_pages = after_index[normalize_url(issue.url)]
            links = {normalize_url(link) for page in source_pages for link in page.links}
            for evidence in issue.evidence:
                if evidence.field != "broken_target":
                    continue
                target = normalize_url(evidence.value.rsplit(" (HTTP ", 1)[0])
                if target in links and _state(target, after_index) != "assessed":
                    return "A previously broken target is still linked but was not assessed in the later audit."
    return None


def _complete_coverage(audit: Audit, indexed: dict[str, list[Page]], assessed: set[str]) -> bool:
    coverage = audit.coverage
    return bool(assessed) and (
        audit.status == "completed"
        and not (coverage.blocked or coverage.failed or coverage.unchecked or coverage.truncated)
        and coverage.attempted == coverage.assessed == len(audit.pages) == len(indexed) == len(assessed)
        and audit.score.assessed_pages == len(assessed)
        and all(_assessed(page) and not page.truncated_fields
                and not (page.structured_data and page.structured_data.truncated) for page in audit.pages)
    )


def compare_audits(before: Audit, after: Audit) -> dict[str, Any]:
    """Compare observations on common assessed URLs; unknown evidence never proves a fix."""
    if before.status not in FINISHED_STATUSES or after.status not in FINISHED_STATUSES:
        raise ValueError("Only finished audits can be compared.")
    if before.mode != after.mode:
        raise ValueError("Compare audits from the same mode; live and sample evidence have different scopes.")
    origin = origin_of(before.origin or before.url)
    if origin != origin_of(after.origin or after.url):
        raise ValueError("Audits must have the same normalized website origin.")
    before_index, after_index = _pages(before, origin), _pages(after, origin)
    before_urls, after_urls = _assessed_urls(before_index), _assessed_urls(after_index)
    common = before_urls & after_urls
    before_findings, after_findings = _findings(before), _findings(after)
    rules_match = before.rules_version == after.rules_version
    versions_match = rules_match and before.score.version == after.score.version
    changes: dict[str, list[dict[str, Any]]] = {status: [] for status in CHANGE_STATUSES}
    for key in sorted(before_findings.keys() | after_findings.keys()):
        earlier, later = before_findings.get(key, []), after_findings.get(key, [])
        is_site = key[3]
        in_common = key[1] in common if not is_site else bool(common) and before_urls == after_urls
        state = _state(key[1], after_index) if not is_site else "unknown"
        if earlier and later and in_common:
            status, reason = "persistent", "The same rule and primary evidence field were observed in both audits."
        elif earlier:
            reason = _resolution_unknown_reason(
                earlier, before, after_index, common, rules_match, target=after,
            )
            status = "unresolved_unknown" if reason else "resolved"
            reason = reason or "Not observed by the same rules with complete required evidence on all affected URLs."
        elif in_common:
            reason = _resolution_unknown_reason(
                later, after, before_index, common, rules_match, target=before,
            )
            status = "unresolved_unknown" if reason else "added"
            reason = (reason.replace("later", "earlier") if reason else
                      "Newly observed within the common assessed scope; this is not a ranking forecast.")
        else:
            # Findings on newly assessed URLs are a coverage change, not evidence of regression.
            continue
        changes[status].append(_change(key, earlier, later, status, reason, state))
    coverage_comparable = before_urls == after_urls and (
        _complete_coverage(before, before_index, before_urls) and _complete_coverage(after, after_index, after_urls)
    )
    if not versions_match:
        score_reason = "Score delta withheld because rule or score versions differ."
    elif not coverage_comparable:
        score_reason = "Score delta withheld: equal assessed URL sets and complete, untruncated coverage are required."
    elif changes["unresolved_unknown"]:
        score_reason = "Score delta withheld because unresolved findings have unknown verification evidence."
    elif before.score.formula != after.score.formula:
        score_reason = "Score delta withheld because the recorded score formulas differ."
    elif before.score.value is None or after.score.value is None:
        score_reason = "Score delta unavailable because one audit has no assessed score."
    else:
        score_reason = "Comparable heuristic scores on the same complete URL scope; this is not a ranking forecast."
    score_delta = (
        after.score.value - before.score.value
        if coverage_comparable and versions_match and not changes["unresolved_unknown"]
        and before.score.formula == after.score.formula
        and before.score.value is not None and after.score.value is not None else None
    )
    limitations = [
        "Only common assessed HTML or HTTP-error URLs are compared. New coverage is not a regression or improvement.",
        "A resolved observation applies only to the recorded rule and fetched evidence; rankings are not measured.",
        "Site-policy findings cannot be marked resolved without retained evidence of a later successful inspection.",
    ]
    if before_urls != after_urls:
        limitations.append("Assessed URL coverage changed; findings outside the common scope are not comparable.")
    if not rules_match:
        limitations.append("Rule versions differ; added and resolved classifications are withheld.")
    if not coverage_comparable:
        limitations.append("At least one audit has incomplete, inconsistent, or truncated coverage.")
    result = {
        "before_audit_id": before.id, "after_audit_id": after.id, "origin": origin,
        "rules_version_before": before.rules_version, "rules_version_after": after.rules_version,
        "score_version_before": before.score.version, "score_version_after": after.score.version,
        "versions_match": versions_match,
        "assessed_urls_before": sorted(before_urls), "assessed_urls_after": sorted(after_urls),
        "common_assessed_urls": sorted(common), "added_assessed_urls": sorted(after_urls - before_urls),
        "removed_assessed_urls": sorted(before_urls - after_urls),
        "coverage_before": before.coverage.model_dump(), "coverage_after": after.coverage.model_dump(),
        "coverage_comparable": coverage_comparable,
        "score_before": before.score.value, "score_after": after.score.value, "score_delta": score_delta,
        "score_delta_reason": score_reason, **changes,
        "counts": {status: len(changes[status]) for status in CHANGE_STATUSES}, "limitations": limitations,
    }
    _bounded(_json(result))
    return result


def _public_history(audit: Audit, dispositions: list[dict] | None) -> list[dict[str, Any]]:
    issue_ids = {issue.id for issue in audit.issues}
    recommendation_ids = {recommendation.id for recommendation in audit.recommendations}
    fields = ("id", "audit_id", "recommendation_id", "issue_id", "rule_id", "url", "status", "reason",
              "decided_at", "recorded_at")
    history = []
    for entry in dispositions or []:
        if not isinstance(entry, dict) or entry.get("audit_id", audit.id) != audit.id:
            continue
        if not (entry.get("issue_id") in issue_ids or entry.get("recommendation_id") in recommendation_ids):
            continue
        if "issue_id" in entry and entry["issue_id"] not in issue_ids:
            continue
        if "recommendation_id" in entry and entry["recommendation_id"] not in recommendation_ids:
            continue
        history.append({field: entry[field] for field in fields
                        if field in entry and (entry[field] is None or isinstance(entry[field], (str, int, bool)))})
    return history


def _report(audit: Audit, dispositions: list[dict] | None) -> dict[str, Any]:
    limitations = [
        "This bounded audit is a fetched snapshot. Unchecked URLs and content outside its scope remain unknown.",
        "Scores are diagnostic heuristics, not measurements or forecasts of search rankings or traffic.",
        "Suggestions need human review. Approval records a decision; it does not verify implementation or results.",
        "AI and sample suggestions are hypotheses, not verified facts or confirmed fixes.",
        "Listed sitemap URLs and search-engine indexing were not verified.",
    ]
    if audit.discovery is None:
        limitations.append("Discovery checks were not recorded for this audit; their outcomes remain unknown.")
    else:
        limitations.extend(audit.discovery.notes)
    if audit.score.breakdown is None:
        limitations.append("A score breakdown was not recorded; the historical score has not been recalculated.")
    limitations.append("Score deductions are diagnostic inputs, not predicted gains. Review decisions do not change the recorded score.")
    if audit.status not in {"completed", "partial"}:
        limitations.append("The audit did not complete normally; retained observations may be incomplete.")
    if audit.mode == "demo":
        limitations.append("Sample mode uses bundled fixtures; it does not describe a live website inspection.")
        if audit.demo_revision is None:
            limitations.append("The sample fixture revision was not recorded; this is a historical demonstration.")
    coverage = audit.coverage
    if coverage.blocked or coverage.failed or coverage.unchecked or coverage.truncated:
        limitations.append("Coverage is incomplete: blocked, failed, unchecked, or truncated evidence is not verified.")
    for page in audit.pages:
        if page.truncated_fields:
            limitations.append(f"Truncated page evidence: {page.url}; fields: {', '.join(page.truncated_fields)}.")
    limitations.extend(audit.warnings)
    recommendations = []
    for recommendation in audit.recommendations:
        verification = ("AI hypothesis; not verified; requires human review."
                        if recommendation.source == "ai" else
                        "Sample hypothesis; not verified; requires human review."
                        if recommendation.source == "demo" else
                        "Rule-based advice from observed evidence; implementation and outcomes are not verified.")
        recommendations.append(recommendation.model_dump() | {"verification": verification})
    return {
        "report_version": "1", "audit_id": audit.id, "url": audit.url, "origin": audit.origin,
        "mode": audit.mode, "demo_revision": audit.demo_revision, "status": audit.status, "created_at": audit.created_at,
        "updated_at": audit.updated_at, "completed_at": audit.completed_at,
        "summary": audit.summary, "rules_version": audit.rules_version, "score": audit.score.model_dump(),
        "coverage": audit.coverage.model_dump(), "ai_status": audit.ai_status,
        "discovery": audit.discovery.model_dump() if audit.discovery else None,
        "recommendation_decision_counts": {
            status: sum(recommendation.status == status for recommendation in audit.recommendations)
            for status in ("pending", "approved", "rejected")
        },
        "human_review": "Pending suggestions require human review; approval does not verify a fix or its outcomes.",
        "pages": [{"url": page.url, "outcome": page.outcome, "status_code": page.status_code,
                   "truncated_fields": list(page.truncated_fields)} for page in audit.pages],
        "findings": [issue.model_dump() for issue in audit.issues], "recommendations": recommendations,
        "review_history": _public_history(audit, dispositions), "limitations": limitations,
    }


def _md(value: Any) -> str:
    value = html.escape(str(value), quote=False)
    return re.sub(r"([\\`*{}\[\]#+!|])", r"\\\1", value).replace("\r", "").replace("\n", "\n  ")


def _markdown(report: dict[str, Any]) -> str:
    score, coverage = report["score"], report["coverage"]
    counts = report["recommendation_decision_counts"]
    sample_revision = ([f"Sample fixture revision: {_md(report['demo_revision'] or 'not recorded')}.", ""]
                       if report["mode"] == "demo" else [])
    lines = [
        "# SEOPilot audit report", "", f"Audit: {_md(report['audit_id'])}", "",
        f"Website: {_md(report['url'])}", "",
        f"Mode: {_md(report['mode'])}; status: {_md(report['status'])}; AI status: {_md(report['ai_status'])}.", "",
        *sample_revision,
        f"Created: {_md(report['created_at'])}; completed: {_md(report['completed_at'] or 'not recorded')}.", "",
        _md(report["summary"]), "", "## Score and coverage", "",
        f"Score: {score['value'] if score['value'] is not None else 'unavailable'} / 100. "
        f"Rules version: {_md(report['rules_version'])}. Score version: {_md(score['version'])}.", "",
        f"Score formula: {_md(score['formula'])}", "",
        "; ".join(f"{field}: {_md(value)}" for field, value in coverage.items()) + ".", "",
    ]
    lines.extend(_score_markdown(score))
    lines.extend([
        "## Human review", "", _md(report["human_review"]), "",
        f"Recommendation decisions: pending {counts['pending']}, approved {counts['approved']}, "
        f"rejected {counts['rejected']}.", "", "## Crawl discovery", "",
    ])
    discovery = report["discovery"]
    if discovery is not None:
        lines.extend([
            f"Robots policy: {_md(discovery['robots_state'])}; sitemap: {_md(discovery['sitemap_state'])}.", "",
            f"Budgeted request attempts: {discovery['request_attempts']}; "
            f"effective minimum delay: {discovery['effective_delay_seconds']} seconds.", "",
        ])
        for probe in discovery["probes"]:
            lines.extend([f"- {_md(probe['kind'])}: {_md(probe['url'])}; {_md(probe['outcome'])}; "
                          f"HTTP {_md(probe['status_code'] or 'not recorded')}. {_md(probe['explanation'])}"])
    else:
        lines.append("Discovery checks were not recorded for this audit; their outcomes remain unknown.")
    lines.extend(["", "## Findings", ""])
    if not report["findings"]:
        lines.extend(["No findings were recorded within the inspected scope; unchecked evidence remains unknown.", ""])
    for finding in report["findings"]:
        lines.extend([
            f"### {_md(finding['title'])}", "",
            f"Rule: {_md(finding['rule_id'])}; severity: {_md(finding['severity'])}; "
            f"source: {_md(finding['source'])}; site finding: {finding['is_site']}.", "",
            f"URL: {_md(finding['url'])}", "", _md(finding["explanation"]), "",
            "Evidence:", "",
        ])
        lines.extend(f"- {_md(evidence['field'])}: {_md(evidence['value'])}" for evidence in finding["evidence"])
        lines.extend(["", f"Suggested fix: {_md(finding['recommended_fix'])}", "",
                      f"Estimated impact: {_md(finding['estimated_impact'])}", ""])
    lines.extend(["## Suggestions", ""])
    if not report["recommendations"]:
        lines.extend(["No suggestions were recorded.", ""])
    for recommendation in report["recommendations"]:
        lines.extend([
            f"### {_md(recommendation['title'])}", "",
            f"Source: {_md(recommendation['source'])}; basis: {_md(recommendation['basis'])}; "
            f"decision: {_md(recommendation['status'])}.", "",
            _md(recommendation["verification"]), "", f"URL: {_md(recommendation['url'])}", "",
            f"Rationale: {_md(recommendation['rationale'])}", "",
            f"Suggested value: {_md(recommendation['suggested_value'] or '(none)')}", "",
            f"Evidence references: {_md(', '.join(recommendation['evidence_ids']) or '(none)')}", "",
        ])
    lines.extend(["## Review history and finding dispositions", ""])
    for entry in report["review_history"]:
        lines.extend(["; ".join(f"{field}: {_md(value)}" for field, value in entry.items()), ""])
    if not report["review_history"]:
        lines.extend(["No additional review history was supplied.", ""])
    lines.extend(["## Unresolved limitations", ""])
    lines.extend(f"- {_md(limitation)}" for limitation in report["limitations"])
    return "\n".join(lines) + "\n"


def _score_markdown(score: dict[str, Any]) -> list[str]:
    lines = ["## Score breakdown", ""]
    detail = score["breakdown"]
    if detail is None:
        return lines + ["A score breakdown was not recorded; the historical score has not been recalculated.", ""]
    lines.extend([
        f"Mean page penalty: {detail['mean_page_penalty'] if detail['mean_page_penalty'] is not None else 'unavailable'}; "
        f"site rule points: {detail['site_rule_points']}; capped site penalty: {detail['site_penalty']} / 20.", "",
        f"Unrounded score: {detail['unrounded_value'] if detail['unrounded_value'] is not None else 'unavailable'}. "
        "Round to the nearest integer (ties to even), then clamp to 0–100. No assessed pages means no score.", "",
    ])
    for page in detail["pages"]:
        lines.extend([f"### {_md(page['url'])}", "",
                      f"Page penalty: {page['penalty']} / 100; raw rule points: {page['rule_points']}.", ""])
        if page["outcome"] == "http_error":
            lines.extend(["HTTP-error override: this page receives 100 penalty points regardless of rule totals.", ""])
        for rule in page["rules"]:
            lines.append(f"- {_md(rule['title'])}; {_md(rule['rule_id'])}; {_md(rule['severity'])}: {rule['points']} raw points.")
        if not page["rules"]:
            lines.append("No page-rule deductions recorded.")
        lines.append("")
    lines.extend(["### Site deductions", ""])
    for rule in detail["site_rules"]:
        lines.append(f"- {_md(rule['title'])}; {_md(rule['rule_id'])}; {_md(rule['severity'])}: {rule['points']} raw points.")
    if not detail["site_rules"]:
        lines.append("No site-rule deductions recorded.")
    lines.extend(["", "### Excluded from the score denominator", ""])
    for page in detail["excluded_pages"]:
        lines.append(f"- {_md(page['url'])}: {_md(page['outcome'])}; HTTP {_md(page['status_code'] or 'not recorded')}.")
    if not detail["excluded_pages"]:
        lines.append("No fetched page records were excluded; this does not establish coverage of undiscovered URLs.")
    return lines + [""]


def _csv_cell(value: Any) -> str:
    cell = "" if value is None else str(value)
    # Leading whitespace can hide formula prefixes in spreadsheet applications.
    first = next((character for character in cell if not character.isspace() or character in "\t\r"), "")
    if first and first in "=+-@\t\r":
        return "'" + cell
    return cell


def _csv(report: dict[str, Any]) -> str:
    columns = ("record_type", "id", "url", "rule_id", "title", "severity", "category", "field", "value",
               "explanation", "recommended_fix", "estimated_impact", "source", "basis", "status", "reason",
               "evidence_ids", "issue_ids", "decided_at")
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\r\n")
    writer.writerow(columns)

    def write(record_type: str, **values: Any) -> None:
        writer.writerow([_csv_cell(record_type if column == "record_type" else values.get(column))
                         for column in columns])

    for field in ("report_version", "audit_id", "url", "origin", "mode", "demo_revision", "status", "created_at", "updated_at",
                  "completed_at", "summary", "rules_version", "ai_status", "human_review"):
        write("audit", field=field, value=report[field])
    for section in ("score", "coverage", "recommendation_decision_counts"):
        for field, value in report[section].items():
            if field != "breakdown":
                write(section, field=field, value=value)
    detail = report["score"]["breakdown"]
    if detail is not None:
        for field in ("mean_page_penalty", "site_rule_points", "site_penalty", "unrounded_value"):
            write("score_breakdown", field=field, value=detail[field])
        for page in detail["pages"]:
            for field in ("rule_points", "penalty"):
                write("page_penalty", id=page["page_id"], url=page["url"], field=field, value=page[field],
                      reason="HTTP-error override: 100" if page["outcome"] == "http_error" else "Page penalty cap: 100")
            for rule in page["rules"]:
                write("page_score_rule", id=page["page_id"], url=page["url"], rule_id=rule["rule_id"], title=rule["title"],
                      severity=rule["severity"], field="raw_points", value=rule["points"], source="deterministic")
        for rule in detail["site_rules"]:
            write("site_score_rule", rule_id=rule["rule_id"], title=rule["title"], severity=rule["severity"],
                  field="raw_points", value=rule["points"], source="deterministic", reason="Combined site cap: 20")
        for page in detail["excluded_pages"]:
            write("excluded_score_page", id=page["page_id"], url=page["url"], field="outcome", value=page["outcome"],
                  status=page["status_code"], reason="Excluded from the assessed-page denominator")
    discovery = report["discovery"]
    if discovery is not None:
        for field in ("robots_state", "sitemap_state", "request_attempts", "effective_delay_seconds"):
            write("discovery", field=field, value=discovery[field])
        for probe in discovery["probes"]:
            write("discovery_probe", url=probe["url"], field=probe["kind"], value=probe["outcome"],
                  status=probe["status_code"], explanation=probe["explanation"])
    for page in report["pages"]:
        write("page", url=page["url"], field="outcome", value=page["outcome"], status=page["status_code"],
              reason=_json(page["truncated_fields"]))
    for finding in report["findings"]:
        values = {field: finding[field] for field in (
            "id", "url", "rule_id", "title", "severity", "category", "explanation", "recommended_fix",
            "estimated_impact", "source",
        )}
        for evidence in finding["evidence"] or [{"field": "", "value": "No retained evidence"}]:
            write("finding", **values, field=evidence["field"], value=evidence["value"],
                  reason=f"site finding: {finding['is_site']}")
    for recommendation in report["recommendations"]:
        write("recommendation", id=recommendation["id"], url=recommendation["url"],
              title=recommendation["title"], severity=recommendation["priority"],
              explanation=recommendation["rationale"], recommended_fix=recommendation["suggested_value"],
              source=recommendation["source"], basis=recommendation["basis"], status=recommendation["status"],
              reason=recommendation["verification"], evidence_ids=_json(recommendation["evidence_ids"]),
              issue_ids=_json(recommendation["issue_ids"]), decided_at=recommendation["decided_at"])
    for entry in report["review_history"]:
        write("review_history", id=entry.get("id"), url=entry.get("url"), rule_id=entry.get("rule_id"),
              status=entry.get("status"), reason=entry.get("reason"), issue_ids=entry.get("issue_id"),
              value=entry.get("recommendation_id"), decided_at=entry.get("decided_at", entry.get("recorded_at")))
    for limitation in report["limitations"]:
        write("limitation", value=limitation)
    return output.getvalue()


def export_audit(audit: Audit, *, format: str = "markdown", dispositions: list[dict] | None = None) -> dict[str, str]:
    """Export a public evidence report without cache, source files, credentials, or provider calls."""
    formats = {"markdown": ("md", "text/markdown; charset=utf-8", _markdown),
               "csv": ("csv", "text/csv; charset=utf-8", _csv),
               "json": ("json", "application/json", lambda report: _json(report, pretty=True))}
    if format not in formats:
        raise ValueError("Unsupported report format. Choose markdown, csv, or json.")
    extension, media_type, render = formats[format]
    content = _bounded(render(_report(audit, dispositions)))
    identifier = re.sub(r"[^A-Za-z0-9_-]", "-", audit.id)[:80] or "audit"
    result = {"filename": f"seopilot-audit-{identifier}.{extension}", "media_type": media_type, "content": content}
    _bounded(_json(result))
    return result
