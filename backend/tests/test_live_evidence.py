from uuid import uuid4

import pytest

from seopilot.fix_engine import compare_live
from seopilot.fix_models import FixRun, FixTarget
from seopilot.models import Audit, Coverage, Evidence, Issue, Page, Score


def comparison_fixture():
    url = "https://example.com/"
    page = Page(url=url, status_code=200, title="", description="Existing description")
    issue = Issue(rule_id="title_missing", title="Missing title", url=url, page_ids=[page.id], severity="High",
                  category="Metadata", explanation="No title", evidence=[Evidence(field="title", value="")],
                  recommended_fix="Write a title")
    before = Audit(url=url, origin="https://example.com", status="completed", pages=[page], issues=[issue],
                   coverage=Coverage(attempted=1, assessed=1), score=Score(value=90, assessed_pages=1))
    after = before.model_copy(deep=True)
    after.id = str(uuid4())
    after.pages[0].title = "Approved title"
    after.issues = []
    after.score.value = 100
    target = FixTarget(url=url, route="/", path="app/page.tsx", title="Approved title", description=None)
    run = FixRun(project_id=str(uuid4()), audit_id=before.id, repository_id=1, base_branch="main", base_sha="a"*40,
                 patch_hash="b"*64, expires_at="2099-01-01T00:00:00+00:00", targets=[target],
                 changed_files=[target.path], changed_lines=2)
    return before, after, run


@pytest.mark.parametrize("status", ["failed", "interrupted", "cancelled"])
def test_unfinished_verification_never_passes_matching_retained_metadata(status):
    before, after, run = comparison_fixture()
    after.status = status
    result = compare_live(before, after, run)
    assert result["status"] == "failed"
    assert result["checks"][0]["passed"] is False
    assert result["resolved"] == result["new"] == []
    assert result["score_comparable"] is False


@pytest.mark.parametrize("field", ["body", "title", "description", "robots", "canonicals"])
def test_truncated_metadata_or_body_never_verifies_a_matching_prefix(field):
    before, after, run = comparison_fixture()
    after.pages[0].truncated_fields = [field]
    result = compare_live(before, after, run)
    assert result["status"] == "failed"
    assert result["score_comparable"] is False


@pytest.mark.parametrize("limit", ["failed", "truncated", "formula"])
def test_metadata_verification_does_not_claim_score_comparability_from_incomplete_coverage(limit):
    before, after, run = comparison_fixture()
    if limit == "failed":
        after.status = "partial"
        after.coverage.failed = 1
        after.coverage.attempted = 2
    elif limit == "truncated":
        after.coverage.truncated = True
    else:
        after.score.formula = "A different scoring formula"
    result = compare_live(before, after, run)
    assert result["status"] == "verified"
    assert result["score_comparable"] is False


def test_absent_finding_needs_its_own_complete_diagnostic_evidence():
    before, after, run = comparison_fixture()
    before.issues[0].rule_id = "json_ld_invalid_json"
    before.issues[0].evidence[0].field = "structured_data"
    result = compare_live(before, after, run)
    assert result["status"] == "verified"
    assert result["resolved"] == []
    assert len(result["unresolved_unknown"]) == 1
    assert not result["score_comparable"]


def test_empty_target_set_and_incompatible_snapshots_fail_closed():
    before, after, run = comparison_fixture()
    run.targets = []
    assert compare_live(before, after, run)["status"] == "failed"
    before, after, run = comparison_fixture()
    after.origin = "https://other.example"
    assert compare_live(before, after, run)["status"] == "failed"
