import pytest

from seopilot.models import Heading, ImageInfo, Page
from seopilot.rules import RuleThresholds, analyze, calculate_score, rule_recommendations


def page(path="/", **values):
    defaults = dict(
        url=f"https://example.com{path}", status_code=200, title="Useful local business services",
        description="Discover our local business services and learn how our team can help with your next project.",
        headings=[Heading(level=1, text="Useful local services")], canonicals=[f"https://example.com{path}"],
    )
    return Page(**(defaults | values))


def test_clean_pages_have_no_issues_and_score_100():
    pages = [page()]
    issues = analyze(pages, "https://example.com", "present", "present")
    assert issues == []
    assert calculate_score(pages, issues).value == 100


def test_metadata_and_image_rules_keep_evidence_and_ignore_decorative_alt():
    p = page(title="", description="", headings=[], canonicals=[], images=[
        ImageInfo(src="/decorative.png", alt=""), ImageInfo(src="/product.png"),
    ])
    issues = analyze([p], "https://example.com")
    by_rule = {issue.rule_id: issue for issue in issues}
    assert set(by_rule) == {"title_missing", "description_missing", "h1_missing", "image_alt_missing", "canonical_missing"}
    assert "/product.png" in str(by_rule["image_alt_missing"].evidence)
    assert "/decorative.png" not in str(by_rule["image_alt_missing"].evidence)
    assert all(issue.evidence and issue.page_ids == [p.id] for issue in issues)
    assert len(rule_recommendations(issues, [p])) == len(issues)


def test_duplicate_groups_score_once_per_affected_page():
    pages = [page("/"), page("/about")]
    issues = analyze(pages, "https://example.com")
    assert {issue.rule_id for issue in issues} == {"title_duplicate", "description_duplicate"}
    assert all(set(issue.page_ids) == {p.id for p in pages} for issue in issues)
    assert calculate_score(pages, issues).value == 90
    assert calculate_score(pages, issues + issues).value == 90


def test_unknown_pages_do_not_inflate_score_and_empty_audit_has_no_score():
    p = page(title="")
    issues = analyze([p], "https://example.com")
    unknown = Page(url="https://example.com/private", outcome="blocked")
    assert calculate_score([p], issues).value == calculate_score([p, unknown], issues).value == 90
    assert calculate_score([unknown], []).value is None


def test_http_error_body_does_not_generate_metadata_rules():
    broken = Page(url="https://example.com/missing", outcome="http_error", status_code=404)
    source = page(links=[broken.url, broken.url, "https://example.com/unchecked"])
    issues = analyze([source, broken], "https://example.com")
    assert {i.rule_id for i in issues} == {"http_error", "broken_internal_link"}
    assert calculate_score([broken], issues).value == 0
    assert len(next(i for i in issues if i.rule_id == "broken_internal_link").evidence) == 1


def test_site_penalties_are_once_per_site_and_unknown_is_not_absent():
    p = page()
    issues = analyze([p], "https://example.com", "absent", "absent", discovery_evidence={
        "robots": [("https://example.com/robots.txt", 404)],
        "sitemap": [("https://example.com/sitemap.xml", 410)],
    })
    assert len(issues) == 2 and all(i.is_site for i in issues)
    assert any("sitemap.xml (HTTP 410)" in e.value for issue in issues for e in issue.evidence)
    assert calculate_score([p], issues).value == 96
    assert calculate_score([p], issues + issues).value == 96
    assert analyze([p], "https://example.com", "unknown", "unknown") == []


def test_thresholds_are_configurable_and_advice_is_a_heuristic():
    p = page(title="Short title", description="x" * 170)
    issues = analyze([p], "https://example.com")
    assert {i.rule_id for i in issues} == {"title_short", "description_long"}
    assert all("heuristic" in i.explanation for i in issues)
    custom = RuleThresholds(title_min=5, title_max=100, description_min=10, description_max=200)
    assert analyze([p], "https://example.com", thresholds=custom) == []


def test_structure_and_indexing_findings_do_not_claim_penalties():
    p = page(
        headings=[Heading(level=1, text="One"), Heading(level=3, text="Skip"), Heading(level=1, text="Two")],
        robots=["index, follow", "noindex"], canonicals=["https://other.example/canonical"],
    )
    issues = analyze([p], "https://example.com")
    assert {i.rule_id for i in issues} == {"h1_multiple", "heading_hierarchy", "indexing_restricted", "canonical_nonself"}
    assert all("guarantee" not in i.explanation.casefold() for i in issues)


def test_no_orphan_or_unconfirmed_broken_link_claims():
    pages = [page(links=["https://example.com/limited"]), Page(
        url="https://example.com/limited", outcome="error", error="timeout",
    )]
    assert analyze(pages, "https://example.com") == []


def test_score_is_consistent_when_equivalent_page_distribution_grows():
    first = page(title="")
    other = page("/other", title="", description="A separate page with useful, distinct information about our local team and the services we provide.")
    assert calculate_score([first], analyze([first], "https://example.com")).value == 90
    assert calculate_score([first, other], analyze([first, other], "https://example.com")).value == 90


def test_empty_canonical_is_invalid_and_transient_targets_are_not_broken():
    source = page(canonicals=[""], links=["https://example.com/busy"])
    busy = Page(url="https://example.com/busy", outcome="http_error", status_code=503)
    issues = analyze([source, busy], "https://example.com")
    assert {issue.rule_id for issue in issues} == {"canonical_invalid", "http_error"}


@pytest.mark.parametrize(("change", "rule"), [
    ({"url": "http://example.com/", "canonicals": ["http://example.com/"]}, "non_https"),
    ({"title": "A" * 61}, "title_long"),
    ({"description": "A short description"}, "description_short"),
    ({"canonicals": ["https://example.com/", "https://example.com/other"]}, "canonical_multiple"),
    ({"canonicals": ["mailto:hello@example.com"]}, "canonical_invalid"),
    ({"canonicals": ["https://[malformed/"]}, "canonical_invalid"),
])
def test_remaining_observed_rules(change, rule):
    issues = analyze([page(**change)], "https://example.com")
    assert {issue.rule_id for issue in issues} == {rule}


def test_intentional_multiple_h1_is_low_priority_manual_review():
    p = page(headings=[Heading(level=1, text="One"), Heading(level=1, text="Two")])
    issues = analyze([p], "https://example.com")
    assert len(issues) == 1
    assert issues[0].rule_id == "h1_multiple" and issues[0].severity == "Low"
    assert "intentional" in issues[0].explanation
