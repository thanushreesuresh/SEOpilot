"""Local developer runs preserve public charges and cannot make paid requests."""

import json

import pytest
from fastapi.testclient import TestClient

from seopilot.app import create_app
from seopilot.developer_audit import run_developer_audit
from seopilot.models import Audit, CrawlOptions
from seopilot.settings import Settings
from seopilot.storage import Store


@pytest.mark.asyncio
async def test_repeated_developer_runs_leave_exhausted_public_allowance_enforced(tmp_path, monkeypatch):
    path = tmp_path / "audit.db"
    store = Store(path)
    for index in range(3):
        audit = Audit(url=f"https://example.org/{index}", origin="https://example.org", allow_ai=False)
        assert store.admit_audit(audit, "127.0.0.1")[1] == "created"
        audit.status = "completed"
        store.save(audit)

    async def processor(audit, saved_store, *, settings):
        assert audit.allow_ai is False and settings.ai_enabled is False
        assert saved_store.get(audit.id).status == "crawling"
        audit.status = "completed"
        saved_store.save(audit)

    monkeypatch.setattr("seopilot.developer_audit.execute", processor)
    for _ in range(4):
        audit = await run_developer_audit("https://example.org/", path, CrawlOptions(), "Owned site pilot")
        assert audit.status == "completed"
        assert "Local developer audit" in store.get(audit.id).business_context
    assert store.quota("127.0.0.1")["used"] == 3
    with store.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM admissions").fetchone()[0] == 3
        assert db.execute("SELECT COUNT(*) FROM ai_calls").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM audits").fetchone()[0] == 7
    with TestClient(create_app(path, start_worker=False, settings=Settings(ai_enabled=False)),
                    base_url="http://localhost", client=("127.0.0.1", 50000)) as http:
        assert http.post("/api/audits", json={"url": "https://example.org/public", "allow_ai": False}).status_code == 429
        # A forged developer flag cannot obtain admission through the public API.
        assert http.post("/api/audits", json={"url": "https://example.org/public", "developer": True}).status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize("url", ["http://127.0.0.1/", "https://user:password@example.org/", "file:///etc/passwd"])
async def test_unsafe_url_is_rejected_before_database_creation(tmp_path, url):
    path = tmp_path / "audit.db"
    with pytest.raises(ValueError):
        await run_developer_audit(url, path, CrawlOptions(), "Owned site pilot")
    assert not path.exists()


@pytest.mark.asyncio
async def test_failure_is_recorded_without_exception_details(tmp_path, monkeypatch):
    path = tmp_path / "audit.db"

    async def fail(*args, **kwargs):
        raise RuntimeError("PRIVATE_FAILURE_CANARY")

    monkeypatch.setattr("seopilot.developer_audit.execute", fail)
    audit = await run_developer_audit("https://example.org/", path, CrawlOptions(), "Owned site pilot")
    saved = Store(path).get(audit.id)
    assert saved.status == "failed" and saved.completed_at
    assert "PRIVATE_FAILURE_CANARY" not in saved.model_dump_json()
    assert saved.allow_ai is False


@pytest.mark.asyncio
async def test_cancelled_developer_run_retains_interrupted_evidence(tmp_path, monkeypatch):
    import asyncio

    path = tmp_path / "audit.db"

    async def cancel(*args, **kwargs):
        raise asyncio.CancelledError()

    monkeypatch.setattr("seopilot.developer_audit.execute", cancel)
    with pytest.raises(asyncio.CancelledError):
        await run_developer_audit("https://example.org/", path, CrawlOptions(), "Owned site pilot")
    store = Store(path)
    audit = store.get(store.history()[0].id)
    assert audit.status == "interrupted" and audit.completed_at


@pytest.mark.asyncio
async def test_developer_run_respects_pending_capacity(tmp_path):
    path = tmp_path / "audit.db"
    store = Store(path)
    for index in range(5):
        assert store.enqueue(Audit(url=f"https://example.org/{index}", origin="https://example.org"))
    with pytest.raises(ValueError, match="capacity"):
        await run_developer_audit("https://example.org/", path, CrawlOptions(), "Owned site pilot")
    assert len(store.history()) == 5


def test_cli_rejects_unsafe_limits_without_creating_database(tmp_path, capsys):
    from seopilot.developer_audit import main

    path = tmp_path / "audit.db"
    assert main(["https://example.org/", "--reason", "Pilot", "--database", str(path), "--pages", "31"]) == 2
    assert json.loads(capsys.readouterr().out)["error"]
    assert not path.exists()


@pytest.mark.asyncio
async def test_dashboard_cancellation_stops_the_developer_processor(tmp_path, monkeypatch):
    import asyncio

    path = tmp_path / "audit.db"
    started, stopped = asyncio.Event(), asyncio.Event()

    async def processor(audit, store, **kwargs):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    monkeypatch.setattr("seopilot.developer_audit.execute", processor)
    task = asyncio.create_task(run_developer_audit("https://example.org/", path, CrawlOptions(), "Pilot"))
    await asyncio.wait_for(started.wait(), 2)
    store = Store(path)
    audit_id = store.history()[0].id
    store.cancel_audit(audit_id)
    result = await asyncio.wait_for(task, 2)
    assert stopped.is_set() and result.status == "cancelled"
    assert store.get(audit_id).status == "cancelled"
