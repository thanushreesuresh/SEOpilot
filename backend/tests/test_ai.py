import asyncio
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from seopilot.ai import AnalysisBundle, Candidate, EvidenceQuote, ReviewBundle, ReviewDecision, enrich
from seopilot.models import Audit, Heading, Page
from seopilot.rules import analyze, rule_recommendations


def audit_fixture():
    page = Page(
        url="https://example.com/", status_code=200, title="", description="",
        headings=[Heading(level=1, text="Handmade pottery in Kochi")],
        text_excerpt="We make handmade pottery in Kochi and offer pottery workshops.",
    )
    audit = Audit(url=page.url, origin="https://example.com", pages=[page])
    audit.issues = analyze(audit.pages, audit.origin)
    audit.recommendations = rule_recommendations(audit.issues, audit.pages)
    return audit


def candidate(audit, **overrides):
    page = audit.pages[0]
    values = dict(
        id="candidate-1", page_id=page.id, kind="title", title="Clarify the page title",
        issue_ids=[audit.issues[0].id],
        quotes=[EvidenceQuote(evidence_id=f"page:{page.id}:text_excerpt", quote="handmade pottery in Kochi")],
        rationale="The visible text identifies handmade pottery and the business location.",
        suggested_value="Handmade Pottery & Workshops in Kochi", priority="High", basis="inferred", target_page_id=None,
    )
    return Candidate(**(values | overrides))


class FakeProvider:
    def __init__(self, candidates, *, reject=False, error=False):
        self.candidates = candidates
        self.reject = reject
        self.error = error
        self.calls = []

    async def generate(self, context):
        self.calls.append(("generate", context))
        if self.error:
            raise RuntimeError("secret-provider-error-never-display")
        return AnalysisBundle(recommendations=self.candidates)

    async def review(self, context, candidates):
        self.calls.append(("review", context))
        return ReviewBundle(decisions=[ReviewDecision(
            candidate_id=c.id, accepted=not self.reject, reason="Checked against quoted evidence.",
        ) for c in candidates])


@pytest.mark.asyncio
async def test_missing_configuration_makes_no_api_calls(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    audit = audit_fixture()
    original = [r.id for r in audit.recommendations]
    await enrich(audit)
    assert audit.ai_status == "unavailable"
    assert [r.id for r in audit.recommendations] == original
    assert audit.summary


@pytest.mark.asyncio
async def test_generation_requires_review_and_keeps_deterministic_recommendations():
    audit = audit_fixture()
    rule_ids = [r.id for r in audit.recommendations]
    provider = FakeProvider([candidate(audit)])
    await enrich(audit, provider=provider)
    assert audit.ai_status == "available"
    assert [name for name, _ in provider.calls] == ["generate", "review"]
    assert [r.id for r in audit.recommendations if r.source == "rule"] == rule_ids
    added = [r for r in audit.recommendations if r.source == "ai"]
    assert len(added) == 1 and added[0].basis == "inferred" and added[0].status == "pending"


@pytest.mark.asyncio
@pytest.mark.parametrize("change", [
    {"page_id": "unknown-page"},
    {"issue_ids": ["unknown-issue"]},
    {"quotes": [EvidenceQuote(evidence_id="unknown-evidence", quote="not observed")]},
    {"quotes": []},
    {"rationale": "This will increase traffic by 40% and guarantee first place."},
    {"suggested_value": "https://fabricated.example/offer"},
    {"kind": "internal_link", "target_page_id": "unknown-target"},
])
async def test_invalid_or_unsupported_candidates_are_never_published(change):
    audit = audit_fixture()
    await enrich(audit, provider=FakeProvider([candidate(audit, **change)]))
    assert not any(r.source == "ai" for r in audit.recommendations)


@pytest.mark.asyncio
async def test_quote_must_be_literal_observed_text():
    audit = audit_fixture()
    bad_quote = EvidenceQuote(evidence_id=f"page:{audit.pages[0].id}:text_excerpt", quote="5000 monthly searches")
    await enrich(audit, provider=FakeProvider([candidate(audit, quotes=[bad_quote])]))
    assert not any(r.source == "ai" for r in audit.recommendations)


@pytest.mark.asyncio
async def test_reviewer_rejection_and_provider_failure_preserve_fallback():
    audit = audit_fixture()
    await enrich(audit, provider=FakeProvider([candidate(audit)], reject=True))
    assert not any(r.source == "ai" for r in audit.recommendations)
    await enrich(audit, provider=FakeProvider([], error=True))
    assert audit.ai_status == "failed"
    assert audit.recommendations
    assert "secret-provider-error" not in str(audit.model_dump())


@pytest.mark.asyncio
async def test_duplicate_and_conflicting_metadata_edits_publish_at_most_one():
    audit = audit_fixture()
    first = candidate(audit)
    conflicting = candidate(audit, id="candidate-2", suggested_value="Pottery Studio in Kochi")
    await enrich(audit, provider=FakeProvider([first, first, conflicting]))
    assert len([r for r in audit.recommendations if r.source == "ai"]) == 1


@pytest.mark.asyncio
async def test_total_timeout_preserves_fallback(monkeypatch):
    audit = audit_fixture()

    class Slow(FakeProvider):
        async def generate(self, context):
            await asyncio.sleep(1)

    monkeypatch.setattr("seopilot.ai.AI_TOTAL_SECONDS", 0.01)
    await enrich(audit, provider=Slow([]))
    assert audit.ai_status == "failed" and audit.recommendations


@pytest.mark.asyncio
async def test_demo_uses_fixture_rules_and_never_live_ai():
    from seopilot.demo import build_demo

    audit = await build_demo()
    assert audit.mode == "demo" and audit.ai_status == "demo"
    assert audit.pages and audit.issues and audit.recommendations
    assert audit.score.value is not None
    assert any(r.source == "demo" for r in audit.recommendations)
    assert not any(r.source == "ai" for r in audit.recommendations)


@pytest.mark.asyncio
@pytest.mark.parametrize("absent", ["OPENAI_API_KEY", "OPENAI_MODEL"])
async def test_each_configuration_name_is_required_before_client_creation(monkeypatch, absent):
    monkeypatch.setenv("OPENAI_API_KEY", "offline-test-placeholder")
    monkeypatch.setenv("OPENAI_MODEL", "offline-model-placeholder")
    monkeypatch.delenv(absent)

    def forbidden(*args):
        raise AssertionError("Provider must not be constructed for incomplete configuration")

    monkeypatch.setattr("seopilot.ai.OpenAIProvider", forbidden)
    audit = audit_fixture()
    await enrich(audit)
    assert audit.ai_status == "unavailable"


@pytest.mark.asyncio
async def test_evidence_from_another_page_is_rejected():
    audit = audit_fixture()
    other = Page(url="https://example.com/about", status_code=200, text_excerpt="unrelated text")
    audit.pages.append(other)
    quote = EvidenceQuote(evidence_id=f"page:{other.id}:text_excerpt", quote="unrelated text")
    await enrich(audit, provider=FakeProvider([candidate(audit, quotes=[quote])]))
    assert not any(r.source == "ai" for r in audit.recommendations)


@pytest.mark.asyncio
async def test_client_cleanup_failure_does_not_override_validated_results(monkeypatch):
    audit = audit_fixture()

    class CloseFailure(FakeProvider):
        async def close(self):
            raise RuntimeError("cleanup detail must not escape")

    monkeypatch.setenv("OPENAI_API_KEY", "offline-test-placeholder")
    monkeypatch.setenv("OPENAI_MODEL", "offline-model-placeholder")
    fake = CloseFailure([candidate(audit)])
    monkeypatch.setattr("seopilot.ai.OpenAIProvider", lambda key, model: fake)
    await enrich(audit)
    assert audit.ai_status == "available"
    assert any(r.source == "ai" for r in audit.recommendations)


@pytest.mark.asyncio
async def test_malformed_provider_schema_falls_back_without_exposing_output():
    audit = audit_fixture()

    class Malformed(FakeProvider):
        async def generate(self, context):
            return {"recommendations": [{"kind": "invented"}], "unexpected": "private-provider-detail"}

    await enrich(audit, provider=Malformed([]))
    assert audit.ai_status == "failed"
    assert audit.recommendations and all(rec.source == "rule" for rec in audit.recommendations)
    assert "private-provider-detail" not in str(audit.model_dump())


@pytest.mark.asyncio
async def test_contradictory_duplicate_reviewer_decisions_fail_closed():
    audit = audit_fixture()

    class Contradictory(FakeProvider):
        async def review(self, context, candidates):
            return ReviewBundle(decisions=[
                ReviewDecision(candidate_id=candidates[0].id, accepted=True, reason="First decision"),
                ReviewDecision(candidate_id=candidates[0].id, accepted=False, reason="Conflicting decision"),
            ])

    await enrich(audit, provider=Contradictory([candidate(audit)]))
    assert not any(rec.source == "ai" for rec in audit.recommendations)


def test_candidate_schema_rejects_unknown_enums():
    with pytest.raises(ValidationError):
        candidate(audit_fixture(), kind="ranking_forecast")


@pytest.mark.asyncio
async def test_responses_transport_uses_structured_formats_no_tools_or_retries(monkeypatch):
    audit = audit_fixture()
    generated = candidate(audit)
    calls = []
    closed = []

    class FakeClient:
        def __init__(self, **kwargs):
            assert kwargs["max_retries"] == 0 and kwargs["timeout"] == 35
            self.responses = self

        async def parse(self, **kwargs):
            calls.append(kwargs)
            if kwargs["text_format"] is AnalysisBundle:
                return SimpleNamespace(output_parsed=AnalysisBundle(recommendations=[generated]))
            return SimpleNamespace(output_parsed=ReviewBundle(decisions=[ReviewDecision(
                candidate_id=generated.id, accepted=True, reason="Grounded in the supplied excerpt.",
            )]))

        async def close(self):
            closed.append(True)

    monkeypatch.setenv("OPENAI_API_KEY", "offline-test-placeholder")
    monkeypatch.setenv("OPENAI_MODEL", "offline-model-placeholder")
    monkeypatch.setattr("openai.AsyncOpenAI", FakeClient)
    await enrich(audit)
    assert audit.ai_status == "available"
    assert len(calls) == 2 and closed == [True]
    assert all(call["store"] is False and "tools" not in call for call in calls)
    assert all(call["model"] == "offline-model-placeholder" for call in calls)
