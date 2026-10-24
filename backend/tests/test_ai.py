import asyncio
import ssl
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from seopilot.ai import (
    MAX_AI_INPUT_BYTES,
    MAX_CONTEXT_BYTES,
    AnalysisBundle,
    Candidate,
    EvidenceQuote,
    OpenAIProvider,
    ReviewBundle,
    ReviewDecision,
    _context,
    enrich,
)
from seopilot.models import Audit, Heading, Page
from seopilot.rules import analyze, rule_recommendations
from seopilot.settings import Settings
from seopilot.storage import Store


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


class RecordingBudget:
    def __init__(self, allowance=20):
        self.calls = []
        self.allowance = allowance

    def reserve_ai_call(self, audit_id, daily_limit, max_per_audit=2):
        if len(self.calls) >= min(self.allowance, daily_limit):
            return False
        self.calls.append((audit_id, daily_limit, max_per_audit))
        return True


@pytest.mark.asyncio
async def test_provider_uses_verified_system_certificate_store(monkeypatch):
    from openai import DefaultAsyncHttpxClient

    captured = {}

    def client_factory(**kwargs):
        captured.update(kwargs)
        return DefaultAsyncHttpxClient(**kwargs)

    monkeypatch.setattr("openai.DefaultAsyncHttpxClient", client_factory)
    provider = OpenAIProvider("offline-test-placeholder", "gpt-6-luna")
    try:
        context = captured.get("verify")
        assert isinstance(context, ssl.SSLContext)
        assert context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname
        assert captured["trust_env"] is False
    finally:
        await provider.close()


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
async def test_key_is_required_before_client_creation(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_MODEL", "gpt-6-luna")

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
    monkeypatch.setenv("OPENAI_MODEL", "gpt-6-luna")
    fake = CloseFailure([candidate(audit)])
    monkeypatch.setattr("seopilot.ai.OpenAIProvider", lambda key, model, **kwargs: fake)
    await enrich(audit, store=RecordingBudget())
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
    transport_settings = []

    class FakeClient:
        def __init__(self, **kwargs):
            assert kwargs["max_retries"] == 0 and kwargs["timeout"] == 35
            assert kwargs["base_url"] == "https://api.openai.com/v1"
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
    monkeypatch.setenv("OPENAI_MODEL", "gpt-6-luna")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://untrusted.example/steal")
    monkeypatch.setattr("openai.DefaultAsyncHttpxClient", lambda **kwargs: transport_settings.append(kwargs))
    monkeypatch.setattr("openai.AsyncOpenAI", FakeClient)
    budget = RecordingBudget()
    await enrich(audit, store=budget)
    assert audit.ai_status == "available"
    assert len(calls) == 2 and closed == [True]
    assert all(call["store"] is False and "tools" not in call for call in calls)
    assert len(budget.calls) == 2
    assert all(call["model"] == "gpt-6-luna" for call in calls)
    assert all(call["max_output_tokens"] == 2500 and call["reasoning"] == {"effort": "low"} for call in calls)
    assert len(transport_settings) == 1 and transport_settings[0]["trust_env"] is False
    assert isinstance(transport_settings[0]["verify"], ssl.SSLContext)
    assert all("offline-test-placeholder" not in str(call) for call in calls)


@pytest.mark.asyncio
@pytest.mark.parametrize("allow_ai,enabled", [(False, True), (True, False)])
async def test_audit_opt_out_and_server_kill_switch_make_no_calls(allow_ai, enabled):
    audit = audit_fixture()
    audit.allow_ai = allow_ai
    provider = FakeProvider([candidate(audit)])
    budget = RecordingBudget()
    await enrich(audit, provider=provider, store=budget, settings=Settings(ai_enabled=enabled))
    assert audit.ai_status == "unavailable"
    assert not provider.calls and not budget.calls
    assert all(rec.source == "rule" for rec in audit.recommendations)


@pytest.mark.asyncio
async def test_model_defaults_to_luna_when_only_key_is_configured(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "offline-test-placeholder")
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    audit = audit_fixture()
    provider = FakeProvider([])
    constructed = []

    def make_provider(key, model, **kwargs):
        constructed.append((model, kwargs))
        return provider

    monkeypatch.setattr("seopilot.ai.OpenAIProvider", make_provider)
    await enrich(audit, store=RecordingBudget())
    assert audit.ai_status == "available"
    assert constructed == [("gpt-6-luna", {"max_output_tokens": 2500})]


@pytest.mark.asyncio
@pytest.mark.parametrize("model", ["", "GPT-6-Luna", "gpt-6", "untrusted-model"])
async def test_unsupported_models_fail_before_sdk_construction(monkeypatch, model):
    monkeypatch.setenv("OPENAI_API_KEY", "offline-test-placeholder")
    monkeypatch.setenv("OPENAI_MODEL", model)

    def forbidden(*args, **kwargs):
        raise AssertionError("Unsupported models must never construct a provider")

    monkeypatch.setattr("seopilot.ai.OpenAIProvider", forbidden)
    audit = audit_fixture()
    await enrich(audit, store=RecordingBudget())
    assert audit.ai_status == "unavailable"
    assert "gpt-6-luna" in audit.warnings[-1]
    assert all(rec.source == "rule" for rec in audit.recommendations)


@pytest.mark.asyncio
async def test_live_provider_without_persistent_budget_fails_closed(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "offline-test-placeholder")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-6-luna")

    def forbidden(*args, **kwargs):
        raise AssertionError("A persistent budget is required")

    monkeypatch.setattr("seopilot.ai.OpenAIProvider", forbidden)
    audit = audit_fixture()
    await enrich(audit)
    assert audit.ai_status == "limited"
    assert all(rec.source == "rule" for rec in audit.recommendations)


@pytest.mark.asyncio
async def test_explicit_live_provider_injection_cannot_bypass_budget_guard():
    class BudgetedProvider(FakeProvider):
        requires_budget = True

    audit = audit_fixture()
    provider = BudgetedProvider([candidate(audit)])
    await enrich(audit, provider=provider)
    assert audit.ai_status == "limited" and not provider.calls


@pytest.mark.asyncio
@pytest.mark.parametrize("limit,expected_calls", [(0, []), (1, ["generate"]), (2, ["generate", "review"])])
async def test_each_generation_and_review_requires_a_durable_reservation(tmp_path, limit, expected_calls):
    audit = audit_fixture()
    store = Store(tmp_path / "budget.db")
    store.save(audit)

    class CheckReservation(FakeProvider):
        async def generate(self, context):
            with store.connection() as db:
                assert db.execute("SELECT COUNT(*) FROM ai_calls").fetchone()[0] == 1
            return await super().generate(context)

        async def review(self, context, candidates):
            with store.connection() as db:
                assert db.execute("SELECT COUNT(*) FROM ai_calls").fetchone()[0] == 2
            return await super().review(context, candidates)

    provider = CheckReservation([candidate(audit)])
    await enrich(audit, provider=provider, store=store, settings=Settings(ai_daily_call_limit=limit))
    assert [name for name, _ in provider.calls] == expected_calls
    assert audit.ai_status == ("available" if limit == 2 else "limited")
    assert sum(rec.source == "ai" for rec in audit.recommendations) == (1 if limit == 2 else 0)
    with store.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM ai_calls").fetchone()[0] == len(expected_calls)


@pytest.mark.asyncio
async def test_failed_generation_keeps_reservation_after_restart(tmp_path):
    path = tmp_path / "budget.db"
    store = Store(path)
    audit = audit_fixture()
    store.save(audit)
    await enrich(audit, provider=FakeProvider([], error=True), store=store, settings=Settings(ai_daily_call_limit=1))
    assert audit.ai_status == "failed"
    restarted = Store(path)
    another = audit_fixture()
    restarted.save(another)
    provider = FakeProvider([candidate(another)])
    await enrich(another, provider=provider, store=restarted, settings=Settings(ai_daily_call_limit=1))
    assert another.ai_status == "limited" and not provider.calls


@pytest.mark.asyncio
async def test_failed_review_is_charged_and_never_publishes_candidates(tmp_path):
    audit = audit_fixture()
    store = Store(tmp_path / "budget.db")
    store.save(audit)

    class BrokenReview(FakeProvider):
        async def review(self, context, candidates):
            raise RuntimeError("private-provider-review-detail")

    await enrich(audit, provider=BrokenReview([candidate(audit)]), store=store)
    assert audit.ai_status == "failed"
    assert all(rec.source == "rule" for rec in audit.recommendations)
    assert "private-provider-review-detail" not in audit.model_dump_json()
    with store.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM ai_calls").fetchone()[0] == 2


@pytest.mark.asyncio
async def test_one_audit_cannot_start_more_than_two_calls_over_its_lifetime(tmp_path):
    audit = audit_fixture()
    store = Store(tmp_path / "budget.db")
    store.save(audit)
    await enrich(audit, provider=FakeProvider([candidate(audit)]), store=store)
    provider = FakeProvider([candidate(audit)])
    await enrich(audit, provider=provider, store=store)
    assert audit.ai_status == "limited" and not provider.calls
    assert sum(rec.source == "ai" for rec in audit.recommendations) == 1


def test_context_has_utf8_byte_limit_and_only_included_evidence():
    import json

    audit = audit_fixture()
    audit.business_context = "界" * 2000
    audit.pages = [Page(
        url=f"https://example.com/{index}", status_code=200, title="界" * 512,
        description="界" * 1000, text_excerpt="界" * 2500,
        headings=[Heading(level=1, text="界" * 3000)],
    ) for index in range(8)]
    audit.issues = analyze(audit.pages, audit.origin)
    context, evidence = _context(audit)
    assert len(json.dumps(context, ensure_ascii=False).encode("utf-8")) <= MAX_CONTEXT_BYTES
    assert len(context["pages"]) <= 4 and len(context["issues"]) <= 20
    included = {key for item in context["pages"] + context["issues"] for key in item["observations"]}
    assert set(evidence) == included


@pytest.mark.asyncio
async def test_oversized_input_is_rejected_before_transport_and_sdk_logs_are_restricted(monkeypatch):
    import logging

    calls = []

    class FakeClient:
        def __init__(self, **kwargs):
            self.responses = self

        async def parse(self, **kwargs):
            calls.append(kwargs)
            raise AssertionError("Oversized input must not be sent")

        async def close(self):
            pass

    monkeypatch.setenv("OPENAI_LOG", "debug")
    monkeypatch.setattr("openai.AsyncOpenAI", FakeClient)
    provider = OpenAIProvider("offline-test-placeholder", "gpt-6-luna")
    with pytest.raises(ValueError, match="fixed size allowance"):
        await provider.generate({"content": "界" * MAX_AI_INPUT_BYTES})
    assert not calls
    assert all(logging.getLogger(name).getEffectiveLevel() >= logging.WARNING for name in ("openai", "httpx", "httpcore"))


@pytest.mark.parametrize("model,cap", [("other-model", 2500), ("gpt-6-luna", 511), ("gpt-6-luna", 2501)])
def test_provider_rejects_unsafe_model_or_output_allowance_before_client(monkeypatch, model, cap):
    def forbidden(**kwargs):
        raise AssertionError("Invalid configuration must not construct a client")

    monkeypatch.setattr("openai.AsyncOpenAI", forbidden)
    with pytest.raises(ValueError, match="Unsupported model"):
        OpenAIProvider("offline-test-placeholder", model, max_output_tokens=cap)
