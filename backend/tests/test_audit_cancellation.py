import asyncio
import threading
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from seopilot.app import create_app
from seopilot.models import Audit, Page, Recommendation
from seopilot.runner import run_queue
from seopilot.storage import Store


def test_queued_cancellation_preserves_admission_and_is_idempotent(tmp_path):
    app = create_app(tmp_path / "cancel.db", start_worker=False)
    with TestClient(app, base_url="http://localhost") as client:
        started = client.post("/api/audits", json={"url": "https://example.com/", "allow_ai": False})
        assert started.status_code == 202
        audit_id = started.json()["id"]
        before = client.get("/api/usage").json()
        response = client.post(f"/api/audits/{audit_id}/cancel", json={})
        assert response.status_code == 200
        result = response.json()
        assert result["status"] == result["progress"]["stage"] == "cancelled"
        assert result["completed_at"] and result["warnings"]
        repeated = client.post(f"/api/audits/{audit_id}/cancel", json={})
        assert repeated.json() == result
        assert client.get("/api/usage").json() == before
        assert app.state.store.claim() is None
        assert client.get(f"/api/audits/{audit_id}/report/json").status_code == 200
        fresh = client.post("/api/audits", json={"url": "https://example.com/", "allow_ai": False})
        assert fresh.status_code == 202 and fresh.json()["id"] != audit_id
        assert client.get("/api/usage").json()["used"] == before["used"] + 1


def test_cancel_routes_reject_finished_missing_forged_and_cross_site_requests(tmp_path):
    app = create_app(tmp_path / "cancel.db", start_worker=False)
    with TestClient(app, base_url="http://localhost") as client:
        sample = client.post("/api/demo-audits", json={}).json()
        assert client.post(f"/api/audits/{sample['id']}/cancel", json={}).status_code == 409
        assert client.post(f"/api/audits/{uuid4()}/cancel", json={}).status_code == 404
        assert client.post("/api/audits/forged/cancel", json={}).status_code == 422
        audit = Audit(url="https://example.com/")
        app.state.store.save(audit)
        path = f"/api/audits/{audit.id}/cancel"
        assert client.post(path, json={}, headers={"Origin": "https://attacker.example"}).status_code == 403
        assert app.state.store.get(audit.id).status == "queued"


def test_stale_worker_saves_cannot_resurrect_cancelled_evidence_or_refund_ai(tmp_path):
    store = Store(tmp_path / "cancel.db")
    audit = Audit(url="https://example.com/", status="reviewing", ai_status="pending",
                  pages=[Page(url="https://example.com/", status_code=200, title="Retained evidence")])
    store.save(audit)
    assert store.reserve_ai_call(audit.id, 20)
    cancelled = store.cancel_audit(audit.id)
    assert cancelled.status == cancelled.ai_status == "cancelled"
    audit.status = "completed"
    audit.pages[0].title = "Stale completion must not overwrite retained evidence"
    store.save(audit)
    assert store.get(audit.id) == cancelled
    assert not store.reserve_ai_call(audit.id, 20)
    assert store.ai_calls_remaining(20) == 19
    restarted = Store(store.path)
    restarted.recover()
    assert restarted.get(audit.id) == cancelled


@pytest.mark.parametrize("stage", ["queued", "crawling", "analyzing", "reviewing"])
def test_cancellation_is_durable_from_every_active_stage(tmp_path, stage):
    store = Store(tmp_path / "cancel.db")
    audit = Audit(url="https://example.com/", status=stage)
    store.save(audit)
    result = store.cancel_audit(audit.id)
    assert result.status == "cancelled"
    assert Store(store.path).get(audit.id) == result


def test_cancelled_rule_recommendations_remain_reviewable_without_changing_evidence(tmp_path):
    app = create_app(tmp_path / "cancel.db", start_worker=False)
    with TestClient(app, base_url="http://localhost") as client:
        recommendation = Recommendation(title="Review the page title", url="https://example.com/",
                                        rationale="Confirm the intended wording", priority="High")
        audit = Audit(url=recommendation.url, status="reviewing", recommendations=[recommendation])
        app.state.store.save(audit)
        cancelled = client.post(f"/api/audits/{audit.id}/cancel", json={}).json()
        decision = client.patch(f"/api/recommendations/{recommendation.id}/decision", json={"status": "approved"})
        assert decision.status_code == 200 and decision.json()["decided_at"]
        saved = app.state.store.get(audit.id)
        assert saved.status == "cancelled" and saved.completed_at == cancelled["completed_at"]
        assert len(app.state.store.decisions(audit.id)) == 1


def test_api_cancels_running_work_and_worker_accepts_the_next_audit(tmp_path):
    started, stopped, next_finished = threading.Event(), threading.Event(), threading.Event()

    async def processor(audit, store):
        if audit.url.endswith("/next"):
            audit.status = "completed"
            store.save(audit)
            next_finished.set()
            return
        audit.pages = [Page(url=audit.url, status_code=200, title="Collected before cancellation")]
        store.save(audit)
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    app = create_app(tmp_path / "cancel.db", processor=processor)
    with TestClient(app, base_url="http://localhost") as client:
        audit_id = client.post("/api/audits", json={"url": "https://example.com/"}).json()["id"]
        assert started.wait(3)
        response = client.post(f"/api/audits/{audit_id}/cancel", json={})
        assert response.status_code == 200
        assert stopped.wait(3)
        saved = client.get(f"/api/audits/{audit_id}").json()
        assert saved["status"] == "cancelled" and saved["pages"][0]["title"] == "Collected before cancellation"
        assert client.post("/api/audits", json={"url": "https://example.com/next"}).status_code == 202
        assert next_finished.wait(3)
        assert client.get("/api/health").status_code == 200


@pytest.mark.asyncio
@pytest.mark.parametrize("user_cancelled", [False, True])
async def test_server_shutdown_cancels_active_child_and_never_restarts_cancelled_work(tmp_path, user_cancelled):
    store = Store(tmp_path / "cancel.db")
    audit = Audit(url="https://example.com/")
    store.enqueue(audit)
    started, stopped = asyncio.Event(), asyncio.Event()

    async def processor(item, repository):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    worker = asyncio.create_task(run_queue(store, processor))
    await asyncio.wait_for(started.wait(), 3)
    if user_cancelled:
        store.cancel_audit(audit.id)
    worker.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(worker, 3)
    assert stopped.is_set()
    assert store.get(audit.id).status == ("cancelled" if user_cancelled else "interrupted")


@pytest.mark.asyncio
@pytest.mark.parametrize("blocking_stage", ["generate", "review"])
async def test_cancel_during_ai_stops_the_provider_and_retains_every_reservation(tmp_path, blocking_stage):
    from seopilot.ai import AnalysisBundle, Candidate, EvidenceQuote, enrich
    from seopilot.rules import analyze, rule_recommendations
    from seopilot.settings import Settings

    store = Store(tmp_path / "cancel.db")
    page = Page(url="https://example.com/", status_code=200, text_excerpt="Handmade pottery in Kochi")
    audit = Audit(url=page.url, origin="https://example.com", pages=[page])
    audit.issues = analyze(audit.pages, audit.origin)
    audit.recommendations = rule_recommendations(audit.issues, audit.pages)
    original_ids = [item.id for item in audit.recommendations]
    store.enqueue(audit)
    started, stopped = asyncio.Event(), asyncio.Event()
    calls = []
    suggestion = Candidate(id="candidate-1", page_id=page.id, kind="title", title="Clarify the title",
        issue_ids=[audit.issues[0].id], quotes=[EvidenceQuote(evidence_id=f"page:{page.id}:text_excerpt",
        quote="Handmade pottery in Kochi")], rationale="The page describes handmade pottery and the location.",
        suggested_value="Handmade Pottery in Kochi", priority="High", basis="inferred", target_page_id=None)

    async def block():
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    class Provider:
        async def generate(self, context):
            calls.append("generate")
            if blocking_stage == "generate":
                await block()
            return AnalysisBundle(recommendations=[suggestion])

        async def review(self, context, candidates):
            calls.append("review")
            await block()

    async def processor(item, repository):
        item.status, item.ai_status = "reviewing", "pending"
        repository.save(item)
        await enrich(item, provider=Provider(), store=repository, settings=Settings())
        item.status = "completed"
        repository.save(item)

    worker = asyncio.create_task(run_queue(store, processor))
    try:
        await asyncio.wait_for(started.wait(), 3)
        store.cancel_audit(audit.id)
        await asyncio.wait_for(stopped.wait(), 3)
        saved = store.get(audit.id)
        assert saved.status == saved.ai_status == "cancelled"
        assert [item.id for item in saved.recommendations] == original_ids
        assert all(item.source == "rule" for item in saved.recommendations)
        assert calls == (["generate"] if blocking_stage == "generate" else ["generate", "review"])
        assert store.ai_calls_remaining(20) == 20 - len(calls)
    finally:
        worker.cancel()
        with pytest.raises(asyncio.CancelledError):
            await worker
