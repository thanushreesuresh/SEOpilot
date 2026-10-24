import time

from fastapi.testclient import TestClient

from seopilot.app import create_app
from seopilot.runner import execute


def test_real_runner_api_history_and_decisions_with_fixture_transport(tmp_path, monkeypatch):
    from seopilot.demo import ORIGIN, build_demo

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)

    async def fixture_crawl(url, options, progress):
        # Only the network seam is replaced: production extraction, rules, scoring,
        # runner, persistence, API serialization and decision handling all execute.
        sample = await build_demo()
        from seopilot.crawler import CrawlResult

        result = CrawlResult(
            pages=sample.pages, warnings=[], coverage=sample.coverage,
            robots_state="present", sitemap_state="absent",
            discovery_evidence={"sitemap": [(ORIGIN + "/sitemap.xml", 404)]},
        )
        await progress(sample.pages, len(sample.pages), result.discovery_snapshot())
        return result

    monkeypatch.setattr("seopilot.crawler.crawl", fixture_crawl)
    path = tmp_path / "workflow.db"
    with TestClient(create_app(path, processor=execute), base_url="http://localhost") as client:
        response = client.post("/api/audits", json={"url": ORIGIN + "/"})
        assert response.status_code == 202
        audit_id = response.json()["id"]
        for _ in range(100):
            result = client.get(f"/api/audits/{audit_id}").json()
            if result["status"] in {"completed", "partial", "failed"}:
                break
            time.sleep(0.05)
        assert result["status"] == "completed", result
        assert result["mode"] == "live" and result["ai_status"] == "unavailable"
        assert result["coverage"]["assessed"] == 4
        assert result["discovery"]["robots_state"] == "present"
        assert result["score"]["value"] is not None
        assert len(result["score"]["breakdown"]["pages"]) == result["score"]["assessed_pages"] == 4
        assert all(issue["evidence"] for issue in result["issues"])
        assert any(issue["rule_id"] == "broken_internal_link" for issue in result["issues"])
        rec_id = result["recommendations"][0]["id"]
        decision = client.patch(f"/api/recommendations/{rec_id}/decision", json={"status": "approved"})
        assert decision.status_code == 200 and decision.json()["decided_at"]
        assert client.get(f"/api/audits/{audit_id}").json()["score"] == result["score"]
        assert client.get("/api/audits").json()[0]["id"] == audit_id
    with TestClient(create_app(path, start_worker=False), base_url="http://localhost") as client:
        restored = client.get(f"/api/audits/{audit_id}").json()
        assert restored["discovery"] == result["discovery"]
        assert restored["score"] == result["score"]
        assert restored["recommendations"][0]["status"] == "approved"
        assert client.patch(f"/api/recommendations/{rec_id}/decision", json={"status": "rejected"}).json()["status"] == "rejected"


def test_restricted_urls_options_and_admission(tmp_path):
    with TestClient(create_app(tmp_path / "limits.db", start_worker=False), base_url="http://localhost") as client:
        for url in ("file:///etc/passwd", "http://127.0.0.1/", "http://169.254.169.254/", "https://user:pass@example.com/"):
            assert client.post("/api/audits", json={"url": url}).status_code == 422
        assert client.post("/api/audits", json={"url": "https://example.com/", "options": {"page_limit": 10000}}).status_code == 422
        for index in range(3):
            assert client.post("/api/audits", json={"url": f"https://example.com/{index}"}).status_code == 202
        assert client.post("/api/audits", json={"url": "https://example.com/fourth"}).status_code == 429


def test_sample_endpoint_is_explicit_and_never_runs_live_provider(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with TestClient(create_app(tmp_path / "demo.db", start_worker=False), base_url="http://localhost") as client:
        result = client.post("/api/demo-audits", json={})
        assert result.status_code == 201
        body = result.json()
        assert body["mode"] == "demo" and body["ai_status"] == "demo"
        assert "Sample" in body["summary"]
        assert body["pages"] and body["issues"]
