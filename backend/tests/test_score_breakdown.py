import csv
import io
import json

import pytest

from seopilot.audit_reporting import export_audit
from seopilot.models import Audit, Evidence, Issue, Page, Score
from seopilot.rules import calculate_score
from seopilot.storage import Store


def finding(page, rule="title_missing", severity="High", *, site=False):
    return Issue(rule_id=rule, title=f"Observed {rule}", url=page.url, page_ids=[] if site else [page.id],
                 severity=severity, category="Fixture", explanation="Recorded fixture evidence.",
                 evidence=[Evidence(field="title", value="(missing)")], recommended_fix="Review this field.", is_site=site)


def test_breakdown_records_unique_rule_inputs_and_exact_average():
    first, second = Page(url="https://example.com/", status_code=200), Page(url="https://example.com/other", status_code=200)
    high, medium = finding(first), finding(first, "description_missing", "Medium")
    score = calculate_score([first, second], [high, medium, high])
    assert score.value == 92 and score.version == "1"
    detail = score.breakdown
    assert detail.mean_page_penalty == 7.5 and detail.unrounded_value == 92.5
    assert [(p.page_id, p.rule_points, p.penalty) for p in detail.pages] == [(first.id, 15, 15), (second.id, 0, 0)]
    assert [(r.rule_id, r.points) for r in detail.pages[0].rules] == [("title_missing", 10), ("description_missing", 5)]
    assert detail.site_penalty == detail.site_rule_points == 0 and not detail.excluded_pages


def test_breakdown_distinguishes_raw_rule_totals_caps_and_http_override():
    page = Page(url="https://example.com/", status_code=200)
    broken = Page(url="https://example.com/broken", status_code=503, outcome="http_error")
    issues = [finding(page, f"rule_{i}", "Critical") for i in range(7)]
    issues += [finding(broken, "http_error", "High"), finding(page, "site_a", "Critical", site=True),
               finding(page, "site_a", "Low", site=True), finding(page, "site_b", "Critical", site=True)]
    score = calculate_score([page, broken], issues)
    detail = score.breakdown
    assert score.value == 0 and detail.unrounded_value == -20
    assert detail.pages[0].rule_points == 140 and detail.pages[0].penalty == 100
    assert detail.pages[1].rule_points == 10 and detail.pages[1].penalty == 100
    assert detail.mean_page_penalty == 100
    assert detail.site_rule_points == 40 and detail.site_penalty == 20
    assert len(detail.site_rules) == 2 and detail.site_rules[0].points == 20


def test_group_rule_is_counted_once_for_each_affected_assessed_page():
    pages = [Page(url=f"https://example.com/{i}", status_code=200) for i in range(2)]
    group = finding(pages[0], "title_duplicate", "Medium")
    group.page_ids = [page.id for page in pages] * 2
    score = calculate_score(pages, [group, group])
    assert score.value == 95 and [p.penalty for p in score.breakdown.pages] == [5, 5]
    assert all(len(p.rules) == 1 for p in score.breakdown.pages)


@pytest.mark.parametrize("outcome,status", [("blocked", None), ("error", None), ("non_html", 200), ("html", None), ("html", 404)])
def test_exclusions_are_recorded_without_improving_the_denominator(outcome, status):
    assessed = Page(url="https://example.com/", status_code=200)
    unknown = Page(url="https://example.com/unknown", outcome=outcome, status_code=status)
    score = calculate_score([assessed, unknown], [finding(assessed)])
    assert score.value == 90 and score.assessed_pages == 1 and len(score.breakdown.pages) == 1
    excluded = score.breakdown.excluded_pages
    assert len(excluded) == 1 and excluded[0].page_id == unknown.id and excluded[0].outcome == outcome
    assert excluded[0].status_code == status
    empty = calculate_score([unknown], [])
    assert empty.value is None and empty.breakdown.mean_page_penalty is None
    assert empty.breakdown.unrounded_value is None and empty.breakdown.pages == []


def test_legacy_score_defaults_and_saved_breakdown_are_not_recomputed(tmp_path):
    assert Score.model_validate({"version": "1", "value": 84, "assessed_pages": 1}).breakdown is None
    page = Page(url="https://example.com/", status_code=200)
    audit = Audit(url=page.url, pages=[page], status="completed", score=calculate_score([page], [finding(page)]))
    store = Store(tmp_path / "score.db")
    store.save(audit)
    audit.pages[0].title = "A changed in-memory value"
    restored = Store(store.path).get(audit.id)
    assert restored.score.value == 90 and restored.score.breakdown == audit.score.breakdown
    assert restored.pages[0].title == ""


def test_score_rounding_remains_nearest_even_and_clamped():
    pages = [Page(url=f"https://example.com/{i}", status_code=200) for i in range(2)]
    score = calculate_score(pages, [finding(pages[0], severity="Medium")])
    assert score.breakdown.unrounded_value == 97.5 and score.value == 98
    assert calculate_score([], []).value is None


@pytest.mark.parametrize("format", ["markdown", "json", "csv"])
def test_score_breakdown_reports_keep_caps_exclusions_and_legacy_limits(format):
    assessed = Page(url="https://example.com/", status_code=200)
    excluded = Page(url="https://example.com/private", outcome="blocked")
    issue = finding(assessed)
    issue.title = '=HYPERLINK("https://example.com","<img src=x>")'
    audit = Audit(url=assessed.url, pages=[assessed, excluded], issues=[issue], status="completed",
                  score=calculate_score([assessed, excluded], [issue]))
    content = export_audit(audit, format=format)["content"]
    if format == "json":
        detail = json.loads(content)["score"]["breakdown"]
        assert detail["pages"][0]["penalty"] == 10 and detail["mean_page_penalty"] == 10
        assert detail["excluded_pages"][0]["url"] == excluded.url
    elif format == "csv":
        rows = list(csv.DictReader(io.StringIO(content)))
        assert any(row["record_type"] == "page_penalty" and row["field"] == "penalty" and row["value"] == "10" for row in rows)
        rule = next(row for row in rows if row["record_type"] == "page_score_rule")
        assert rule["title"].startswith("'=HYPERLINK") and rule["value"] == "10"
        assert any(row["record_type"] == "excluded_score_page" and row["url"] == excluded.url for row in rows)
        assert not any(row["field"] == "breakdown" and row["value"].startswith("{") for row in rows)
    else:
        assert "Mean page penalty: 10.0" in content and "Page penalty: 10 / 100" in content
        assert excluded.url in content and "&lt;img src=x&gt;" in content
    audit.score.breakdown = None
    legacy = export_audit(audit, format=format)["content"]
    assert "A score breakdown was not recorded; the historical score has not been recalculated." in legacy
