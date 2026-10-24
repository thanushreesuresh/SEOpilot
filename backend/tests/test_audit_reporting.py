import csv
import io
import json

import pytest

from seopilot.audit_reporting import MAX_REPORT_BYTES, compare_audits, export_audit
from seopilot.models import Audit, Coverage, Evidence, Issue, Page, Recommendation, Score, StructuredDataSummary


def page(path="/", **values):
    return Page(**({"url": f"https://example.com{path}", "status_code": 200} | values))


def issue(target, rule_id="title_missing", field="title", **values):
    return Issue(**({
        "rule_id": rule_id, "title": "Missing title", "url": target.url,
        "page_ids": [target.id], "severity": "High", "category": "Metadata",
        "explanation": "No title was observed.", "evidence": [Evidence(field=field, value="(missing)")],
        "recommended_fix": "Write a descriptive title.",
    } | values))


def audit(pages=None, issues=None, **values):
    pages = [page()] if pages is None else pages
    assessed = sum(p.outcome in {"html", "http_error"} and p.status_code is not None for p in pages)
    return Audit(**({
        "url": "https://example.com/", "origin": "https://example.com", "status": "completed",
        "completed_at": "2026-10-25T00:00:00+00:00", "pages": pages, "issues": issues or [],
        "coverage": Coverage(attempted=len(pages), assessed=assessed),
        "score": Score(value=90, assessed_pages=assessed),
    } | values))


def test_comparison_tracks_persistent_added_resolved_with_stable_identity():
    before_page, after_page = page(), page()
    before_issues = [issue(before_page), issue(before_page, "description_missing", "description")]
    after_issues = [issue(after_page), issue(after_page, "h1_missing", "h1_count")]
    before, after = audit([before_page], before_issues), audit([after_page], after_issues)
    result = compare_audits(before, after)
    assert result["counts"] == {"added": 1, "persistent": 1, "resolved": 1, "unresolved_unknown": 0}
    assert result["persistent"][0]["before_issue_ids"] == [before_issues[0].id]
    assert result["persistent"][0]["after_issue_ids"] == [after_issues[0].id]
    assert result["resolved"][0]["rule_id"] == "description_missing"
    stable_id = result["persistent"][0]["stable_id"]
    before_issues[0].id = "another-id"
    before_issues[0].evidence[0].id = "another-evidence-id"
    assert compare_audits(before, after)["persistent"][0]["stable_id"] == stable_id


def test_normalized_unicode_origin_url_and_fragment_compare_without_network():
    before_page = page(url="https://BÜCHER.example:443/café#old")
    after_page = page(url="https://xn--bcher-kva.example/caf%C3%A9#new")
    before = audit([before_page], [issue(before_page)], origin="https://BÜCHER.example:443")
    after = audit([after_page], [issue(after_page)], origin="https://xn--bcher-kva.example")
    result = compare_audits(before, after)
    assert result["origin"] == "https://xn--bcher-kva.example"
    assert result["counts"]["persistent"] == 1
    assert result["common_assessed_urls"] == ["https://xn--bcher-kva.example/caf%C3%A9"]


def test_duplicate_group_representative_url_and_page_order_do_not_change_finding_identity():
    first_before, second_before = page("/a"), page("/b")
    first_after, second_after = page("/a"), page("/b")
    before_issue = issue(first_before, "title_duplicate", "title",
                         page_ids=[first_before.id, second_before.id])
    after_issue = issue(second_after, "title_duplicate", "title",
                        page_ids=[second_after.id, first_after.id])
    result = compare_audits(audit([first_before, second_before], [before_issue]),
                            audit([second_after, first_after], [after_issue]))
    assert result["counts"] == {"added": 0, "persistent": 2, "resolved": 0, "unresolved_unknown": 0}
    assert {finding["url"] for finding in result["persistent"]} == {first_before.url, second_before.url}
    assert len({finding["stable_id"] for finding in result["persistent"]}) == 2


def test_duplicate_group_cannot_resolve_when_another_affected_url_is_unchecked():
    first, second = page("/a"), page("/b")
    duplicate = issue(first, "title_duplicate", "title", page_ids=[first.id, second.id])
    result = compare_audits(audit([first, second], [duplicate]), audit([page("/a")]))
    assert result["resolved"] == []
    assert len(result["unresolved_unknown"]) == 2


@pytest.mark.parametrize("changes", [
    {"origin": "https://other.example"}, {"origin": "http://example.com"},
    {"status": "crawling"}, {"mode": "demo"},
])
def test_incompatible_audits_are_rejected(changes):
    with pytest.raises(ValueError):
        compare_audits(audit(), audit(**changes))


@pytest.mark.parametrize("status", ["completed", "partial", "failed", "interrupted"])
def test_finished_audits_can_be_inspected_but_incomplete_score_is_not_compared(status):
    result = compare_audits(audit(), audit(status=status))
    assert result["score_delta"] == (0 if status == "completed" else None)


@pytest.mark.parametrize("status", ["failed", "interrupted"])
@pytest.mark.parametrize("absent_in", ["before", "after"])
def test_unfinished_analysis_cannot_turn_missing_findings_into_added_or_resolved(status, absent_in):
    before_page, after_page = page(title=""), page(title="")
    before = audit([before_page], [issue(before_page)], score=Score())
    after = audit([after_page], [issue(after_page)], score=Score())
    without_analysis = before if absent_in == "before" else after
    without_analysis.status = status
    without_analysis.issues = []
    result = compare_audits(before, after)
    assert result["versions_match"] is True
    assert result["rules_version_before"] == result["rules_version_after"] == "1"
    assert result["added"] == result["resolved"] == []
    assert result["counts"]["unresolved_unknown"] == 1
    assert "analysis" in result["unresolved_unknown"][0]["reason"].lower()
    assert result["score_delta"] is None


@pytest.mark.parametrize("status", ["failed", "interrupted"])
def test_observed_findings_can_persist_even_when_the_audit_did_not_finish_normally(status):
    before_page, after_page = page(title=""), page(title="")
    result = compare_audits(audit([before_page], [issue(before_page)]),
                            audit([after_page], [issue(after_page)], status=status))
    assert result["counts"] == {"added": 0, "persistent": 1, "resolved": 0, "unresolved_unknown": 0}


@pytest.mark.parametrize(("outcome", "state"), [("blocked", "blocked"), ("error", "unknown"),
                                                  ("non_html", "unchecked")])
def test_unknown_or_unchecked_url_cannot_resolve_a_finding(outcome, state):
    before_page = page()
    result = compare_audits(audit([before_page], [issue(before_page)]),
                            audit([page(outcome=outcome, status_code=None)], status="partial"))
    assert result["resolved"] == []
    assert result["unresolved_unknown"][0]["after_state"] == state
    assert result["score_delta"] is None
    assert result["removed_assessed_urls"] == [before_page.url]


def test_removed_url_is_unchecked_and_new_coverage_is_not_an_added_finding():
    before_page, after_page = page("/old"), page("/new")
    result = compare_audits(audit([before_page], [issue(before_page)]),
                            audit([after_page], [issue(after_page)], score=Score(value=100, assessed_pages=1)))
    assert result["added"] == result["resolved"] == []
    assert result["unresolved_unknown"][0]["after_state"] == "unchecked"
    assert result["added_assessed_urls"] == [after_page.url]
    assert result["score_delta"] is None


@pytest.mark.parametrize("truncated_field", ["title", "body"])
def test_truncated_evidence_cannot_resolve_a_metadata_finding(truncated_field):
    before_page, after_page = page(), page(truncated_fields=[truncated_field])
    result = compare_audits(audit([before_page], [issue(before_page)]), audit([after_page]))
    assert result["resolved"] == []
    assert "truncat" in result["unresolved_unknown"][0]["reason"].lower()
    assert result["score_delta"] is None


def test_http_error_replacement_does_not_prove_html_metadata_was_fixed():
    before_page = page()
    after_page = page(outcome="http_error", status_code=500)
    result = compare_audits(audit([before_page], [issue(before_page)]),
                            audit([after_page], [issue(after_page, "http_error", "status_code")]))
    assert result["resolved"] == []
    assert len(result["unresolved_unknown"]) == 1


def test_rule_version_changes_withhold_added_and_resolved_and_score_delta():
    before_page, after_page = page(), page()
    result = compare_audits(audit([before_page], [issue(before_page)], rules_version="1"),
                            audit([after_page], [issue(after_page, "new_rule", "title")], rules_version="2"))
    assert result["added"] == result["resolved"] == []
    assert len(result["unresolved_unknown"]) == 2
    assert result["versions_match"] is False
    assert result["score_delta"] is None


def test_newly_observed_finding_is_unknown_when_earlier_field_was_truncated():
    before_page, after_page = page(truncated_fields=["title"]), page()
    result = compare_audits(audit([before_page]), audit([after_page], [issue(after_page)]))
    assert result["added"] == []
    assert len(result["unresolved_unknown"]) == 1
    assert "earlier" in result["unresolved_unknown"][0]["reason"]


def test_old_unknown_structured_data_summary_cannot_prove_a_new_or_resolved_diagnostic():
    before_page, after_page = page(), page(structured_data=StructuredDataSummary(blocks=0))
    diagnostic = issue(after_page, "json_ld_invalid_json", "structured_data")
    result = compare_audits(audit([before_page]), audit([after_page], [diagnostic]))
    assert result["added"] == []
    assert len(result["unresolved_unknown"]) == 1
    result = compare_audits(audit([after_page], [diagnostic]), audit([before_page]))
    assert result["resolved"] == []
    assert len(result["unresolved_unknown"]) == 1


def test_internal_structured_data_truncation_cannot_resolve_diagnostics_or_compare_scores():
    before_page = page(structured_data=StructuredDataSummary(blocks=1))
    after_page = page(structured_data=StructuredDataSummary(blocks=1, truncated=True))
    diagnostic = issue(before_page, "json_ld_invalid_json", "structured_data")
    result = compare_audits(audit([before_page], [diagnostic]), audit([after_page]))
    assert result["resolved"] == []
    assert len(result["unresolved_unknown"]) == 1
    assert result["score_delta"] is None


def test_score_version_change_keeps_rule_comparison_but_withholds_score_delta():
    before_page = page()
    result = compare_audits(audit([before_page], [issue(before_page)]),
                            audit(score=Score(value=100, assessed_pages=1, version="2")))
    assert len(result["resolved"]) == 1
    assert result["score_delta"] is None
    assert result["score_version_after"] == "2"


def test_score_delta_requires_complete_equal_coverage_and_reports_actual_delta():
    before, after = audit(), audit(score=Score(value=100, assessed_pages=1))
    assert compare_audits(before, after)["score_delta"] == 10
    after.coverage.unchecked = 2
    assert compare_audits(before, after)["score_delta"] is None
    after.coverage.unchecked = 0
    after.coverage.assessed = 9
    assert compare_audits(before, after)["score_delta"] is None


def test_site_absence_is_unknown_without_observed_after_policy_state():
    before_page = page()
    site_issue = issue(before_page, "sitemap_absent", "inspected_url", is_site=True,
                       url="https://example.com", page_ids=[])
    result = compare_audits(audit([before_page], [site_issue]), audit())
    assert result["resolved"] == []
    assert result["unresolved_unknown"][0]["is_site"] is True


def test_unchecked_broken_link_target_does_not_make_source_link_resolved():
    target = page("/missing", outcome="http_error", status_code=404)
    source = page(links=[target.url])
    broken = issue(source, "broken_internal_link", "broken_target",
                   evidence=[Evidence(field="broken_target", value=f"{target.url} (HTTP 404)")])
    result = compare_audits(audit([source, target], [broken]), audit([page(links=[target.url])]))
    assert result["resolved"] == []
    assert "target" in result["unresolved_unknown"][0]["reason"].lower()


def test_report_default_includes_evidence_limitations_versions_and_human_review():
    target = page(truncated_fields=["body"])
    finding = issue(target)
    suggestion = Recommendation(source="ai", kind="title", title="Candidate title", url=target.url,
                                rationale="A hypothesis from context.", suggested_value="Better café title",
                                priority="High", basis="inferred")
    result = export_audit(audit([target], [finding], recommendations=[suggestion], ai_status="available",
                                warnings=["Discovery was incomplete."]))
    assert result["media_type"].startswith("text/markdown")
    assert result["filename"].endswith(".md")
    content = result["content"]
    for expected in (finding.recommended_fix, finding.estimated_impact, "(missing)", "deterministic",
                     "formula", "Rules version", "Score version", "AI status", "pending", "human review",
                     "hypothesis", "not verified", "Discovery was incomplete", "truncated"):
        assert expected.lower() in content.lower()


def test_json_report_selects_public_fields_and_filters_decisions_and_unrelated_inputs(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "private-environment-token")
    target = page(text_excerpt="A private cached excerpt that is unnecessary to export")
    finding = issue(target)
    recommendation = Recommendation(title="Review title", url=target.url, rationale="Inspect evidence",
                                    priority="High", status="approved")
    value = audit([target], [finding], recommendations=[recommendation], business_context="private business context")
    decisions = [
        {"audit_id": value.id, "recommendation_id": recommendation.id, "status": "approved",
         "decided_at": "2026-10-25T00:00:00Z", "token": "private-dict-token", "source_html": "private html"},
        {"audit_id": value.id, "issue_id": finding.id, "status": "not_applicable", "reason": "Intentional",
         "recorded_at": "2026-10-25T00:00:01Z"},
        {"audit_id": "another-audit", "issue_id": finding.id, "status": "rejected"},
        {"audit_id": value.id, "issue_id": "unknown-issue", "status": "rejected"},
    ]
    content = export_audit(value, format="json", dispositions=decisions)["content"]
    report = json.loads(content)
    assert report["recommendation_decision_counts"] == {"pending": 0, "approved": 1, "rejected": 0}
    assert len(report["review_history"]) == 2
    assert report["review_history"][1]["reason"] == "Intentional"
    assert all(secret not in content for secret in ["private-environment-token", "private-dict-token",
                                                   "private html", "private business context", "private cached excerpt"])


@pytest.mark.parametrize("payload", ["=HYPERLINK(\"https://bad.example\")", "+SUM(1,2)", "-2+3", "@SUM(1)",
                                     "\t=1", "\r=1", "  =1", "\n\t=1", "\u2003@SUM(1)",
                                     " \tordinary", " \rordinary", "\u2003\tordinary"])
def test_csv_neutralizes_formula_injection_in_every_dynamic_cell(payload):
    target = page()
    finding = issue(target, title=payload, recommended_fix=payload, estimated_impact=payload,
                    evidence=[Evidence(field=payload, value=payload)])
    report = export_audit(audit([target], [finding]), format="csv")
    rows = list(csv.reader(io.StringIO(report["content"])))
    assert len(rows) > 1
    cells = [cell for row in rows for cell in row]
    assert payload not in cells
    assert "'" + payload in cells


@pytest.mark.parametrize("format", ["markdown", "csv", "json"])
def test_all_report_formats_refuse_oversized_output_without_truncation(format):
    target = page()
    finding = issue(target, explanation="é" * MAX_REPORT_BYTES)
    with pytest.raises(ValueError, match="limit|large|MiB"):
        export_audit(audit([target], [finding]), format=format)


def test_report_format_is_validated_and_report_is_deterministic():
    value = audit()
    with pytest.raises(ValueError, match="format"):
        export_audit(value, format="html")
    assert export_audit(value) == export_audit(value)


def test_report_unicode_round_trips_and_filename_cannot_escape_a_download_directory():
    target = page()
    value = audit([target], [issue(target, title="Café 🪴 — മലയാളം")], id="../unsafe/\\audit")
    report = export_audit(value, format="json")
    assert json.loads(report["content"])["findings"][0]["title"] == "Café 🪴 — മലയാളം"
    assert not any(char in report["filename"] for char in "/\\")


def test_comparison_output_is_bounded_in_utf8_bytes_without_silent_truncation():
    target = page()
    before = audit([target], [issue(target, title="é" * MAX_REPORT_BYTES)])
    with pytest.raises(ValueError, match="limit|large|MiB"):
        compare_audits(before, audit())
