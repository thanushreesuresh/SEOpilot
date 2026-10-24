import pytest

from seopilot.extraction import extract_page
from seopilot.models import Audit, Score
from seopilot.rules import RULES_VERSION, analyze
from seopilot.storage import Store


def findings(source):
    page = extract_page("https://example.com/", source)
    return [item for item in analyze([page], "https://example.com") if item.category == "Structured data"]


@pytest.mark.parametrize("source,code", [
    ('{"@type":', "json_ld_invalid_json"),
    ('{"@type":"Thing","@type":"Person"}', "json_ld_duplicate_key"),
    ('{"value":NaN}', "json_ld_non_finite_number"),
    ('42', "json_ld_invalid_root"),
    ('{"@context":"https://schema.org","@graph":[3]}', "json_ld_invalid_graph"),
])
def test_jsonld_diagnostics_have_bounded_evidence(source, code):
    issues = findings(f'<script type="application/ld+json">{source}</script>')
    issue = next(item for item in issues if item.rule_id == code)
    assert issue.severity == "Medium" and issue.source == "deterministic"
    assert issue.evidence[0].field == "structured_data"
    assert "eligibility" in issue.explanation


def test_custom_context_is_review_guidance_and_absence_creates_no_finding():
    assert findings("<title>Ordinary page</title>") == []
    assert findings('<script type="application/ld+json">{"@context":"https://schema.org","@type":"Organization"}</script>') == []
    issue = findings('<script type="application/ld+json">{"@context":"https://example.com/vocabulary","@type":"CustomType"}</script>')[0]
    assert issue.rule_id == "json_ld_nonstandard_context"
    assert issue.severity == "Low" and "can be valid" in issue.recommended_fix


def test_rule_version_changes_do_not_rewrite_legacy_history(tmp_path):
    store = Store(tmp_path/"versions.db")
    audit = Audit(url="https://example.com/", origin="https://example.com")
    store.save(audit)
    assert RULES_VERSION == "2"
    loaded = store.get(audit.id)
    assert loaded.rules_version == "1" and Score().version == "1"
