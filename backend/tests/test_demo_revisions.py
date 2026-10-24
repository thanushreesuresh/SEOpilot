import asyncio
import json
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from seopilot.app import create_app
from seopilot.audit_reporting import export_audit
from seopilot.demo import build_demo
from seopilot.models import Audit
from seopilot.storage import Store


def test_upgrade_creates_current_sample_without_rewriting_legacy_or_usage(tmp_path, monkeypatch):
    from seopilot.demo import DEMO_REVISION

    async def forbidden(*args, **kwargs):
        raise AssertionError("The offline demo must not use network or AI services.")

    monkeypatch.setattr("seopilot.network.fetch", forbidden)
    monkeypatch.setattr("seopilot.ai.enrich", forbidden)
    fixed_time = time.time()
    monkeypatch.setattr("seopilot.storage.time.time", lambda: fixed_time)
    path = tmp_path / "upgrade.db"
    with TestClient(create_app(path, start_worker=False), base_url="http://localhost") as client:
        store = client.app.state.store
        legacy = asyncio.run(build_demo())
        legacy.demo_revision = None
        legacy.score.breakdown = None
        legacy.discovery = None
        store.save(legacy)
        store.decide(legacy.recommendations[0].id, "approved")
        with store.connection() as db:
            old_payload = json.loads(db.execute("SELECT payload FROM audits WHERE id=?", (legacy.id,)).fetchone()[0])
            old_payload.pop("demo_revision")
            legacy_blob = json.dumps(old_payload)
            db.execute("UPDATE audits SET payload=? WHERE id=?", (legacy_blob, legacy.id))
        original = store.get(legacy.id).model_dump()
        # Keep existing accepted admissions and reservations: a demo upgrade is
        # not a way to reset the owner's limits.
        for index in range(3):
            live = client.post("/api/audits", json={"url": f"https://example.com/{index}", "allow_ai": False}).json()
        assert store.reserve_ai_call(live["id"], 20)
        before = client.get("/api/usage").json()
        assert before["remaining"] == 0
        response = client.post("/api/demo-audits", json={"demo_revision": "client-controlled"})
        assert response.status_code == 201
        current = response.json()
        assert current["id"] != legacy.id and current["demo_revision"] == DEMO_REVISION
        assert current["mode"] == "demo" and current["ai_status"] == "demo" and current["allow_ai"] is False
        assert current["score"]["breakdown"] and current["discovery"]
        assert client.get("/api/usage").json() == before
        assert store.get(legacy.id).model_dump() == original
        assert store.decisions(legacy.id)[0]["status"] == "approved"
        with store.connection() as db:
            assert db.execute("SELECT payload FROM audits WHERE id=?", (legacy.id,)).fetchone()[0] == legacy_blob
        reused = client.post("/api/demo-audits", json={}).json()
        assert reused == current
        current_id = current["id"]
    with TestClient(create_app(path, start_worker=False), base_url="http://localhost") as client:
        assert client.post("/api/demo-audits", json={}).json()["id"] == current_id
        assert client.get("/api/usage").json() == before
        assert client.get(f"/api/audits/{legacy.id}").json() == original


def test_current_sample_is_reused_even_beyond_the_latest_100_audits(tmp_path):
    store = Store(tmp_path / "history.db")
    sample = asyncio.run(build_demo())
    sample.created_at = "2000-01-01T00:00:00+00:00"
    saved = store.get_or_create_demo(sample)
    for index in range(101):
        store.save(Audit(url=f"https://example.com/{index}", status="completed"))
    assert all(item.id != sample.id for item in store.history())
    assert store.get_or_create_demo(asyncio.run(build_demo())).id == saved.id


def test_concurrent_sample_requests_persist_one_result_and_its_decisions(tmp_path):
    path = tmp_path / "concurrent.db"
    store = Store(path)
    candidates = [asyncio.run(build_demo()) for _ in range(4)]

    def save(candidate):
        return Store(path).get_or_create_demo(candidate)

    with ThreadPoolExecutor(max_workers=4) as pool:
        saved = list(pool.map(save, candidates))
    assert len({audit.id for audit in saved}) == 1
    assert len(store.history()) == 1
    recommendation = saved[0].recommendations[0]
    store.decide(recommendation.id, "rejected")
    repeated = store.get_or_create_demo(asyncio.run(build_demo()))
    assert repeated.recommendations[0].status == "rejected"
    assert len(store.decisions(repeated.id)) == 1


@pytest.mark.parametrize("changes", [
    {"mode": "live"}, {"demo_revision": None}, {"status": "failed"}, {"allow_ai": True}, {"ai_status": "available"},
])
def test_only_completed_explicit_offline_samples_enter_revision_reuse(tmp_path, changes):
    store = Store(tmp_path / "invalid.db")
    candidate = asyncio.run(build_demo())
    for name, value in changes.items():
        setattr(candidate, name, value)
    with pytest.raises(ValueError, match="offline sample"):
        store.get_or_create_demo(candidate)
    assert store.history() == []


def test_revision_is_parameterized_and_legacy_contract_stays_optional(tmp_path):
    assert Audit(url="https://example.com/").demo_revision is None
    store = Store(tmp_path / "parameter.db")
    candidate = asyncio.run(build_demo())
    candidate.demo_revision = "revision' OR 1=1 --"
    first = store.get_or_create_demo(candidate)
    next_revision = asyncio.run(build_demo())
    assert store.get_or_create_demo(next_revision).id != first.id
    assert len(store.history()) == 2


@pytest.mark.parametrize("changes", [{"status": "failed"}, {"mode": "live"}])
def test_matching_revision_on_unusable_record_does_not_replace_a_current_sample(tmp_path, changes):
    store = Store(tmp_path / "unusable.db")
    unusable = asyncio.run(build_demo())
    for name, value in changes.items():
        setattr(unusable, name, value)
    store.save(unusable)
    current = store.get_or_create_demo(asyncio.run(build_demo()))
    assert current.id != unusable.id
    assert current.mode == "demo" and current.status == "completed"
    assert store.get(unusable.id).model_dump() == unusable.model_dump()


@pytest.mark.parametrize("format", ["markdown", "csv", "json"])
def test_reports_identify_sample_revision_without_rewriting_legacy(format):
    from seopilot.demo import DEMO_REVISION

    sample = asyncio.run(build_demo())
    report = export_audit(sample, format=format)["content"]
    assert DEMO_REVISION in report
    if format == "json":
        assert json.loads(report)["demo_revision"] == DEMO_REVISION
    sample.demo_revision = None
    original = sample.model_dump()
    legacy = export_audit(sample, format=format)["content"]
    assert "The sample fixture revision was not recorded; this is a historical demonstration." in legacy
    assert sample.model_dump() == original


def test_reused_samples_keep_the_existing_short_burst_guard(tmp_path):
    with TestClient(create_app(tmp_path / "burst.db", start_worker=False), base_url="http://localhost") as client:
        samples = [client.post("/api/demo-audits", json={}) for _ in range(10)]
        assert all(response.status_code == 201 for response in samples)
        assert len({response.json()["id"] for response in samples}) == 1
        blocked = client.post("/api/demo-audits", json={})
        assert blocked.status_code == 429 and blocked.headers["Retry-After"] == "60"
        assert len(client.get("/api/audits").json()) == 1
        usage = client.get("/api/usage").json()
        assert usage["used"] == 0 and usage["ai_calls_remaining"] == 20
