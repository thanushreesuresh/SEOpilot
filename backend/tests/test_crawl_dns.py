"""Dashboard workers use an explicit resolver without weakening address checks."""

import time

import pytest
from fastapi.testclient import TestClient

from seopilot.app import create_app
from seopilot.network import NetworkResponse
from seopilot.settings import Settings


def test_dns_choice_is_explicit_and_validated(monkeypatch):
    monkeypatch.delenv("SEOPILOT_CRAWL_DNS", raising=False)
    assert Settings.from_env().crawl_dns == "system"
    monkeypatch.setenv("SEOPILOT_CRAWL_DNS", "google")
    assert Settings.from_env().crawl_dns == "google"
    monkeypatch.setenv("SEOPILOT_CRAWL_DNS", "untrusted-resolver")
    with pytest.raises(ValueError, match="SEOPILOT_CRAWL_DNS"):
        Settings.from_env()


@pytest.mark.parametrize("mode,restricted,assessed", [
    ("system", False, 0), ("google", False, 1), ("google", True, 0),
])
def test_dashboard_worker_dns_and_saved_report(tmp_path, monkeypatch, mode, restricted, assessed):
    calls, connections = [], []

    async def system(host, port):
        calls.append("system")
        return ["8.8.8.8", "64:ff9b::808:808"]

    async def google(host, port):
        calls.append("google")
        return ["8.8.8.8", "127.0.0.1"] if restricted else ["8.8.8.8"]

    async def transport(url, address, timeout, limit):
        connections.append(address)
        if url.endswith(("robots.txt", "sitemap.xml", "sitemap_index.xml")):
            return NetworkResponse(404, {"content-type": "text/plain"}, b"not found")
        return NetworkResponse(200, {"content-type": "text/html"},
                               b"<html><head><title>Real fixture title</title></head>"
                               b"<body><h1>Fixture evidence</h1></body></html>")

    monkeypatch.setattr("seopilot.network.resolve_addresses", system)
    monkeypatch.setattr("seopilot.developer_dns.resolve_google", google)
    monkeypatch.setattr("seopilot.network.fetch_pinned", transport)
    config = Settings(ai_enabled=False, crawl_dns=mode)
    with TestClient(create_app(tmp_path / "audit.db", settings=config), base_url="http://localhost") as client:
        started = client.post("/api/audits", json={"url": "https://example.org/", "allow_ai": False,
                                                  "options": {"page_limit": 1, "max_depth": 0}})
        assert started.status_code == 202
        audit_id = started.json()["id"]
        for _ in range(120):
            audit = client.get(f"/api/audits/{audit_id}").json()
            if audit["status"] in {"completed", "partial", "failed"}:
                break
            time.sleep(0.05)
        assert audit["coverage"]["assessed"] == assessed
        assert set(calls) == {mode}
        assert audit["ai_status"] == "unavailable"
        report = client.get(f"/api/audits/{audit_id}/report/markdown")
        assert report.status_code == 200
        if assessed:
            assert connections and set(connections) == {"8.8.8.8"}
            assert audit["pages"][0]["title"] == "Real fixture title"
            assert audit["score"]["value"] is not None
            assert "Analyzed 1 pages" in report.json()["content"]
            assert any("Google HTTPS" in note for note in audit["discovery"]["notes"])
        else:
            assert not connections
            assert audit["score"]["value"] is None
            assert "unknown" in audit["summary"].lower()
            assert "Only public website addresses" in audit["pages"][0]["error"]
            assert "unknown" in report.json()["content"].lower()
        with client.app.state.store.connection() as db:
            assert db.execute("SELECT COUNT(*) FROM ai_calls").fetchone()[0] == 0


@pytest.mark.asyncio
async def test_explicit_resolver_overrides_config_without_false_provenance(tmp_path, monkeypatch):
    from seopilot.crawler import CrawlResult
    from seopilot.models import Audit
    from seopilot.runner import execute
    from seopilot.storage import Store

    async def injected(host, port):
        raise AssertionError("The fixture crawler should not make network calls")

    async def crawler(url, options, progress, *, resolver):
        assert resolver is injected
        return CrawlResult()

    monkeypatch.setattr("seopilot.crawler.crawl", crawler)
    audit = Audit(url="https://example.org/", origin="https://example.org", allow_ai=False)
    store = Store(tmp_path / "override.db")
    store.enqueue(audit)
    await execute(audit, store, settings=Settings(ai_enabled=False, crawl_dns="google"), resolver=injected)
    assert not any("Google HTTPS" in note for note in audit.discovery.notes)
    assert audit.status == "failed" and "unknown" in audit.summary
