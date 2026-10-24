"""Connection diagnostics disclose setting presence, never credentials or paths."""

from itertools import product
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from seopilot.app import create_app
from seopilot.github_app import GitHubClient, GithubConfig, GitHubError, Repository
from seopilot.settings import Settings

CANARY = "private-connection-canary"
REPOSITORY = Repository(7, 3, "owner", "site", "main", "R_7")


@pytest.mark.parametrize("present", list(product((False, True), repeat=3)))
async def test_setting_checklist_only_reports_presence(present, tmp_path, monkeypatch):
    app_id, path, owners = present
    config = GithubConfig(9 if app_id else None, tmp_path / CANARY if path else None,
                          (CANARY,) if owners else ())
    client = GitHubClient(config)

    def forbidden(*args, **kwargs):
        pytest.fail("Inspecting setting presence must not read a private key")

    try:
        monkeypatch.setattr(Path, "read_bytes", forbidden)
        status = client.status()
        assert status["setup_checks"] == [
            {"setting": "GITHUB_APP_ID", "present": app_id},
            {"setting": "GITHUB_APP_PRIVATE_KEY_PATH", "present": path},
            {"setting": "GITHUB_APP_OWNERS", "present": owners},
        ]
        assert status["configured"] is all(present)
        assert CANARY not in str(status)
    finally:
        await client.close()


@pytest.fixture
def connection(tmp_path, monkeypatch):
    def forbidden(request):
        pytest.fail("Connection fixtures must not access a live GitHub endpoint")

    transport = httpx.AsyncClient(transport=httpx.MockTransport(forbidden))
    github = GitHubClient(GithubConfig(9, tmp_path / CANARY, (CANARY,)), client=transport)
    app = create_app(tmp_path / "fresh.db", start_worker=False, github_client=github,
                     settings=Settings(ai_enabled=False))
    with TestClient(app, base_url="http://localhost") as client:
        yield client, github, app
        client.portal.call(transport.aclose)


def test_missing_settings_do_not_attempt_authentication(connection, monkeypatch):
    client, github, app = connection
    github.config = GithubConfig(9, None, (CANARY,))

    async def forbidden():
        pytest.fail("Incomplete setup must not call GitHub")

    monkeypatch.setattr(github, "list_repositories", forbidden)
    response = client.get("/api/github/connection")
    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "setup_required" and not body["configured"]
    assert body["repositories"] == [] and body["checked_at"]
    assert body["setup_checks"][1]["present"] is False
    assert CANARY not in response.text
    assert app.state.store.quota("unknown")["used"] == 0
    assert app.state.store.ai_calls_remaining(20) == 20


@pytest.mark.parametrize("repositories, expected", [([], "no_repositories"), ([REPOSITORY], "ready")])
def test_verified_connection_distinguishes_empty_installations(connection, monkeypatch, repositories, expected):
    client, github, _ = connection

    async def installed():
        return repositories

    monkeypatch.setattr(github, "list_repositories", installed)
    response = client.get("/api/github/connection")
    body = response.json()
    assert response.status_code == 200 and body["state"] == expected
    assert body["configured"] and body["checked_at"]
    assert len(body["repositories"]) == len(repositories)
    assert all(check["present"] for check in body["setup_checks"])
    assert CANARY not in response.text


@pytest.mark.parametrize("code, expected", [
    ("credentials", "credentials_error"), ("not_configured", "credentials_error"),
    ("forbidden", "access_denied"), ("not_found", "access_denied"),
    ("limited", "rate_limited"), ("unavailable", "unavailable"),
    ("invalid_response", "unavailable"), (CANARY, "unavailable"),
])
def test_github_error_codes_use_fixed_safe_guidance(connection, monkeypatch, caplog, code, expected):
    client, github, _ = connection

    async def failure():
        raise GitHubError(CANARY, code)

    monkeypatch.setattr(github, "list_repositories", failure)
    response = client.get("/api/github/connection")
    body = response.json()
    assert response.status_code == 200 and body["state"] == expected
    assert body["configured"] and body["repositories"] == []
    assert body["checked_at"] and CANARY not in response.text
    assert CANARY not in caplog.text


def test_unknown_failure_is_sanitized_and_refresh_replaces_failed_state(connection, monkeypatch, caplog):
    client, github, _ = connection

    async def failure():
        raise RuntimeError(CANARY)

    monkeypatch.setattr(github, "list_repositories", failure)
    response = client.get("/api/github/connection")
    assert response.json()["state"] == "unavailable"
    assert CANARY not in response.text and CANARY not in caplog.text

    async def recovered():
        return [REPOSITORY]

    monkeypatch.setattr(github, "list_repositories", recovered)
    recovered_body = client.get("/api/github/connection").json()
    assert recovered_body["state"] == "ready" and len(recovered_body["repositories"]) == 1


def test_unreadable_local_key_never_reaches_github(connection):
    client, _, _ = connection
    response = client.get("/api/github/connection")
    assert response.json()["state"] == "credentials_error"
    assert CANARY not in response.text


def test_revocation_drops_previously_verified_repositories(connection, monkeypatch):
    client, github, _ = connection

    async def installed():
        return [REPOSITORY]

    monkeypatch.setattr(github, "list_repositories", installed)
    assert client.get("/api/github/connection").json()["state"] == "ready"

    async def revoked():
        raise GitHubError(CANARY, "forbidden")

    monkeypatch.setattr(github, "list_repositories", revoked)
    response = client.get("/api/github/connection")
    assert response.json()["state"] == "access_denied"
    assert response.json()["repositories"] == [] and CANARY not in response.text
