"""Invalid optional integration settings cannot disable deterministic auditing."""

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from seopilot.app import create_app
from seopilot.crawler import CrawlResult
from seopilot.demo import ORIGIN, build_demo
from seopilot.fix_models import Project
from seopilot.github_app import GitHubClient, GithubConfig
from seopilot.settings import Settings

CANARY = "private-invalid-setting-canary"


def set_app_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("GITHUB_APP_ID", "9")
    monkeypatch.setenv("GITHUB_APP_PRIVATE_KEY_PATH", str(tmp_path / f"{CANARY}.pem"))
    monkeypatch.setenv("GITHUB_APP_OWNERS", "owner")


@pytest.fixture(autouse=True)
def no_github_or_private_key_access(monkeypatch):
    async def forbidden_request(*args, **kwargs):
        pytest.fail("Invalid settings must not make GitHub requests")

    def forbidden_read(*args, **kwargs):
        pytest.fail("Setup isolation must not read a private key")

    monkeypatch.setattr(GitHubClient, "_response", forbidden_request)
    monkeypatch.setattr(Path, "read_bytes", forbidden_read)


@pytest.mark.parametrize("setting, value", [
    ("GITHUB_APP_ID", CANARY), ("GITHUB_APP_ID", "0"),
    ("GITHUB_APP_OWNERS", "owner/" + CANARY), ("GITHUB_APP_OWNERS", "owner_" + CANARY),
])
def test_invalid_optional_settings_keep_api_and_sample_available(tmp_path, monkeypatch, caplog, setting, value):
    set_app_environment(monkeypatch, tmp_path)
    monkeypatch.setenv(setting, value)
    app = create_app(tmp_path / "fresh.db", start_worker=False, settings=Settings(ai_enabled=False))
    with TestClient(app, base_url="http://localhost") as client:
        assert client.get("/api/health").status_code == 200
        response = client.get("/api/github/connection")
        body = response.json()
        assert response.status_code == 200 and body["state"] == "invalid_settings"
        assert not body["configured"] and body["repositories"] == []
        assert all(check["present"] for check in body["setup_checks"])
        assert CANARY not in response.text and CANARY not in repr(app.state.github.config)
        sample = client.post("/api/demo-audits", json={}).json()
        assert sample["mode"] == "demo" and sample["pages"] and sample["score"]["value"] is not None
        assert len(client.get("/api/audits").json()) == 1
        denied = client.post("/api/projects", json={"name": "Blocked connection", "production_origin": ORIGIN,
            "repository_id": 7, "installation_id": 3, "base_branch": "main", "confirms_ownership": True})
        assert denied.status_code == 403 and CANARY not in denied.text
        assert app.state.store.quota("unknown")["used"] == 0
        assert app.state.store.ai_calls_remaining(20) == 20
    assert CANARY not in caplog.text


def test_unexpandable_key_path_reports_safe_configuration_error(tmp_path, monkeypatch, caplog):
    set_app_environment(monkeypatch, tmp_path)

    def invalid_home(*args, **kwargs):
        raise RuntimeError(CANARY)

    monkeypatch.setattr(Path, "expanduser", invalid_home)
    with TestClient(create_app(tmp_path / "fresh.db", start_worker=False), base_url="http://localhost") as client:
        response = client.get("/api/github/connection")
        assert response.json()["state"] == "invalid_settings"
        assert CANARY not in response.text and client.get("/api/health").status_code == 200
    assert CANARY not in caplog.text


@pytest.mark.parametrize("configured", [False, True])
async def test_client_factory_retains_normal_missing_and_valid_settings(tmp_path, monkeypatch, configured):
    if configured:
        set_app_environment(monkeypatch, tmp_path)
    client = GitHubClient.from_env()
    try:
        assert client.config.configured is configured
        assert client.status()["invalid_settings"] is False
        assert all(check["present"] is configured for check in client.status()["setup_checks"])
    finally:
        await client.close()


def test_unexpected_programming_errors_are_not_hidden(monkeypatch):
    def failure(*args, **kwargs):
        raise TypeError("Unexpected programming error")

    monkeypatch.setattr(GithubConfig, "from_env", failure)
    with pytest.raises(TypeError, match="Unexpected programming error"):
        GitHubClient.from_env()


@pytest.fixture
def offline_pages(monkeypatch):
    async def fixture_crawl(url, options, progress):
        sample = await build_demo()
        result = CrawlResult(pages=sample.pages, coverage=sample.coverage)
        await progress(result.pages, len(result.pages), result.discovery_snapshot())
        return result

    monkeypatch.setattr("seopilot.crawler.crawl", fixture_crawl)


def test_real_runner_history_and_decisions_survive_invalid_setup_and_restart(tmp_path, monkeypatch, offline_pages):
    set_app_environment(monkeypatch, tmp_path)
    monkeypatch.setenv("GITHUB_APP_ID", CANARY)
    path = tmp_path / "persistent.db"
    with TestClient(create_app(path, settings=Settings(ai_enabled=False)), base_url="http://localhost") as client:
        response = client.post("/api/audits", json={"url": ORIGIN + "/", "allow_ai": False})
        assert response.status_code == 202
        audit_id = response.json()["id"]
        for _ in range(100):
            audit = client.get(f"/api/audits/{audit_id}").json()
            if audit["status"] in {"completed", "partial", "failed"}:
                break
            time.sleep(0.05)
        assert audit["status"] == "completed" and audit["pages"] and audit["issues"]
        recommendation_id = audit["recommendations"][0]["id"]
        decision = client.patch(f"/api/recommendations/{recommendation_id}/decision", json={"status": "approved"})
        assert decision.status_code == 200 and decision.json()["decided_at"]
        before = client.get("/api/usage").json()
        assert before["used"] == 1 and before["ai_calls_remaining"] == 20
    monkeypatch.setenv("GITHUB_APP_ID", "9")
    with TestClient(create_app(path, start_worker=False), base_url="http://localhost") as client:
        assert client.app.state.github.config.configured
        restored = client.get(f"/api/audits/{audit_id}").json()
        assert restored["score"] == audit["score"] and restored["issues"] == audit["issues"]
        assert restored["recommendations"][0]["status"] == "approved"
        after = client.get("/api/usage").json()
        assert after["used"] == 1 and after["ai_calls_remaining"] == 20
        assert client.get("/api/health").status_code == 200


def test_queued_work_resumes_after_restart_with_invalid_optional_setup(tmp_path, monkeypatch, offline_pages):
    path = tmp_path / "queued.db"
    with TestClient(create_app(path, start_worker=False), base_url="http://localhost") as client:
        response = client.post("/api/audits", json={"url": ORIGIN + "/", "allow_ai": False})
        assert response.status_code == 202 and response.json()["status"] == "queued"
        audit_id = response.json()["id"]
    monkeypatch.setenv("GITHUB_APP_ID", CANARY)
    app = create_app(path, settings=Settings(ai_enabled=False))
    with TestClient(app, base_url="http://localhost") as client:
        for _ in range(100):
            audit = client.get(f"/api/audits/{audit_id}").json()
            if audit["status"] in {"completed", "partial", "failed"}:
                break
            time.sleep(0.05)
        assert audit["status"] == "completed" and audit["score"]["assessed_pages"] == 4
        assert len(client.get("/api/audits").json()) == 1
        assert client.get("/api/usage").json()["used"] == 1
        assert app.state.store.ai_calls_remaining(20) == 20
        assert client.get("/api/github/connection").json()["state"] == "invalid_settings"


async def test_invalid_setup_discards_values_and_preserves_partial_presence(monkeypatch):
    monkeypatch.setenv("GITHUB_APP_ID", CANARY)
    client = GitHubClient.from_env()
    try:
        assert client.config.app_id is None and client.config.private_key_path is None and not client.config.owners
        assert [check["present"] for check in client.status()["setup_checks"]] == [True, False, False]
        assert client.status()["invalid_settings"] and CANARY not in repr(client.config)
    finally:
        await client.close()


def test_disconnect_remains_available_after_environment_becomes_invalid(tmp_path, monkeypatch):
    set_app_environment(monkeypatch, tmp_path)
    app = create_app(tmp_path / "fresh.db", start_worker=False)
    with TestClient(app, base_url="http://localhost") as client:
        project = app.state.store.fixes.connect(Project(name="Retained project", production_origin=ORIGIN,
            installation_id=3, repository_id=7, repository_owner="owner", repository_name="site", base_branch="main"))
        old_client = app.state.github
        monkeypatch.setenv("GITHUB_APP_ID", CANARY)
        response = client.post(f"/api/projects/{project.id}/disconnect", json={})
        assert response.status_code == 200 and not response.json()["connected"]
        assert old_client._client.is_closed
        status = client.get("/api/github/connection")
        assert status.json()["state"] == "invalid_settings" and CANARY not in status.text
        assert client.get("/api/health").status_code == 200
