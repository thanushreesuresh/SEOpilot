"""No test credentials or source files leave the injected GitHub transport."""

import base64
import hashlib
import json
from datetime import UTC, datetime, timedelta

import httpx
import jwt
import pytest

from seopilot.github_app import (
    MAX_ARTIFACT,
    PERMISSIONS,
    GitHubClient,
    GithubConfig,
    GitHubError,
    Repository,
)

NOW = datetime(2026, 10, 25, tzinfo=UTC)
BASE = "a" * 40
HEAD = "b" * 40
REPO = Repository(7, 3, "owner", "site", "main", "R_7")


def installation(**updates):
    return {"id": 3, "app_id": 9, "account": {"login": "owner"}, "suspended_at": None,
            "repository_selection": "selected", "permissions": PERMISSIONS, **updates}


def repository(**updates):
    return {"id": 7, "owner": {"login": "owner"}, "name": "site", "default_branch": "main",
            "node_id": "R_7", "archived": False, "disabled": False, **updates}


def pull(**updates):
    return {"number": 4, "head": {"repo": {"id": 7}, "ref": "seopilot/fix", "sha": HEAD},
            "base": {"repo": {"id": 7}, "ref": "main"}, "draft": True, "state": "open",
            "merged_at": None, **updates}


@pytest.fixture
async def make_client(monkeypatch, tmp_path):
    clients = []

    def create(routes=None, *, clock=None):
        seen = []
        routes = routes or {}

        def handle(request):
            seen.append(request)
            path = request.url.path
            key = (request.method, path)
            if key in routes:
                value = routes[key]
                if callable(value):
                    value = value(request)
                if isinstance(value, Exception):
                    raise value
                if isinstance(value, httpx.Response):
                    return value
                return httpx.Response(200, json=value)
            if path == "/app/installations/3":
                return httpx.Response(200, json=installation())
            if path == "/app/installations/3/access_tokens":
                return httpx.Response(201, json={"token": "test-installation-token",
                    "expires_at": (NOW + timedelta(hours=1)).isoformat(), "permissions": PERMISSIONS})
            if path == "/repositories/7":
                return httpx.Response(200, json=repository())
            return httpx.Response(404, json={"message": "Do not expose response-canary-private-value"})

        transport_client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
        client = GitHubClient(GithubConfig(9, tmp_path / "ignored.pem", ("owner",)),
                              client=transport_client, clock=clock or (lambda: NOW))
        monkeypatch.setattr(client, "_jwt", lambda: "test-app-jwt")
        clients.append(transport_client)
        return client, seen

    yield create
    for client in clients:
        await client.aclose()


def test_config_is_safe_and_validated(monkeypatch, tmp_path):
    for name in ("GITHUB_APP_ID", "GITHUB_APP_OWNERS", "GITHUB_APP_PRIVATE_KEY_PATH"):
        monkeypatch.delenv(name, raising=False)
    assert not GithubConfig.from_env().configured
    monkeypatch.setenv("GITHUB_APP_ID", "9")
    monkeypatch.setenv("GITHUB_APP_OWNERS", "Owner, owner, other")
    monkeypatch.setenv("GITHUB_APP_PRIVATE_KEY_PATH", str(tmp_path / "private.pem"))
    config = GithubConfig.from_env()
    assert config.configured and config.owners == ("owner", "other")
    assert "private.pem" not in repr(config)
    monkeypatch.setenv("GITHUB_APP_OWNERS", "owner/../../other")
    with pytest.raises(ValueError, match="owner names"):
        GithubConfig.from_env()
    monkeypatch.setenv("GITHUB_APP_OWNERS", "owner")
    monkeypatch.setenv("GITHUB_APP_ID", "not-an-id")
    with pytest.raises(ValueError, match="positive integer"):
        GithubConfig.from_env()


async def test_unconfigured_and_private_key_failure_are_sanitized(tmp_path):
    client = GitHubClient(GithubConfig())
    try:
        assert client.status()["configured"] is False
        with pytest.raises(GitHubError, match="incomplete"):
            client._jwt()
        client.config = GithubConfig(9, tmp_path / "private-source-canary", ("owner",))
        with pytest.raises(GitHubError) as failure:
            client._jwt()
        assert failure.value.code == "credentials"
        assert "private-source-canary" not in str(failure.value)
    finally:
        await client.close()


async def test_app_jwt_uses_rsa_short_lifetime_and_server_only_key(tmp_path):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    filename = tmp_path / "test-app-key.pem"
    filename.write_bytes(private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                               serialization.NoEncryption()))
    client = GitHubClient(GithubConfig(9, filename, ("owner",)))
    try:
        token = client._jwt()
        claims = jwt.decode(token, private.public_key(), algorithms=["RS256"])
        assert claims["iss"] == "9" and claims["exp"] - claims["iat"] == 600
        assert set(claims) == {"iat", "exp", "iss"}
        assert str(filename) not in json.dumps(client.status()) and token not in repr(client._tokens)
    finally:
        await client.close()


async def test_authorization_scopes_token_and_rechecks_installed_repository(make_client):
    client, seen = make_client()
    assert await client.authorize(3, 7) == REPO
    assert await client.authorize(3, 7) == REPO
    tokens = [json.loads(request.content) for request in seen if request.method == "POST"]
    assert tokens == [{"permissions": PERMISSIONS, "repository_ids": [7]}]
    assert len([request for request in seen if request.url.path == "/repositories/7"]) == 2
    assert all(request.url.host == "api.github.com" and request.url.scheme == "https" for request in seen)
    assert all(request.headers["x-github-api-version"] == "2026-03-10" for request in seen)
    assert "token" not in json.dumps(client.status()).lower()
    client.forget()
    assert not client._tokens


@pytest.mark.parametrize("item", [installation(account={"login": "attacker"}),
    installation(suspended_at=NOW.isoformat()), installation(app_id=123),
    installation(repository_selection="all"), installation(permissions={"administration": "write"})])
async def test_unapproved_or_overprivileged_installation_is_rejected(make_client, item):
    client, seen = make_client({("GET", "/app/installations/3"): item})
    with pytest.raises(GitHubError) as failure:
        await client.authorize(3, 7)
    assert failure.value.code == "forbidden"
    assert len(seen) == 1


@pytest.mark.parametrize("item", [repository(id=8), repository(owner={"login": "attacker"}),
                                   repository(archived=True), repository(name="../escape")])
async def test_forged_repository_identity_is_rejected(make_client, item):
    client, _ = make_client({("GET", "/repositories/7"): item})
    with pytest.raises(GitHubError):
        await client.authorize(3, 7)


@pytest.mark.parametrize("installation_id,repo_id", [(True, 7), (0, 7), (3, True), (3, -7), ("3", 7)])
async def test_ids_require_positive_integers(make_client, installation_id, repo_id):
    client, seen = make_client()
    with pytest.raises(GitHubError) as failure:
        await client.authorize(installation_id, repo_id)
    assert failure.value.code == "invalid"
    assert not seen


async def test_installed_repository_list_uses_metadata_only_discovery(make_client):
    client, seen = make_client({
        ("GET", "/app/installations"): [installation(), installation(id=4, account={"login": "attacker"})],
        ("GET", "/installation/repositories"): {"total_count": 1, "repositories": [repository()]},
    })
    assert await client.list_repositories() == [REPO]
    creation = next(request for request in seen if request.method == "POST")
    assert json.loads(creation.content) == {"permissions": {"metadata": "read"}}
    assert not any("/4/" in request.url.path for request in seen)


async def test_token_is_refreshed_before_expiry_and_revocation_clears_cache(make_client):
    clock = [NOW]
    client, seen = make_client(clock=lambda: clock[0])
    await client.authorize(3, 7)
    clock[0] = NOW + timedelta(minutes=59, seconds=30)
    await client.authorize(3, 7)
    assert len([request for request in seen if request.method == "POST"]) == 2
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(
        lambda request: httpx.Response(401, json={"message": "secret-response-canary"})))
    with pytest.raises(GitHubError) as failure:
        await client.authorize(3, 7)
    assert failure.value.code == "credentials" and not client._tokens
    assert "canary" not in str(failure.value)
    await client._client.aclose()


async def test_expired_token_response_is_rejected(make_client):
    client, _ = make_client({("POST", "/app/installations/3/access_tokens"):
                            {"token": "private-credential-canary", "expires_at": NOW.isoformat()}})
    with pytest.raises(GitHubError) as failure:
        await client.authorize(3, 7)
    assert failure.value.code == "credentials" and "canary" not in str(failure.value)


def blob(value):
    raw = value.encode("utf-8")
    sha = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    return sha, {"encoding": "base64", "sha": sha, "content": base64.b64encode(raw).decode()}


async def test_sources_are_bounded_static_app_router_files_only(make_client):
    source = 'export const metadata = { title: "Café 日本", description: "A description" };'
    page_sha, page_blob = blob(source)
    package_sha, package_blob = blob('{"dependencies":{"next":"16.4.3"}}')
    client, _ = make_client({
        ("GET", f"/repos/owner/site/git/trees/{BASE}"): {"truncated": False, "tree": [
            {"path": "web/src/app/page.tsx", "type": "blob", "mode": "100644", "sha": page_sha, "size": 100},
            {"path": "web/package.json", "type": "blob", "mode": "100644", "sha": package_sha, "size": 100},
            {"path": "web/.env", "type": "blob", "mode": "100644", "sha": BASE, "size": 100},
            {"path": "web/next.config.ts", "type": "blob", "mode": "100644", "sha": BASE, "size": 100},
        ]},
        ("GET", f"/repos/owner/site/git/blobs/{page_sha}"): page_blob,
        ("GET", f"/repos/owner/site/git/blobs/{package_sha}"): package_blob,
    })
    result = await client.sources(REPO, BASE, "web")
    assert result == {"web/src/app/page.tsx": source, "web/package.json": '{"dependencies":{"next":"16.4.3"}}'}


@pytest.mark.parametrize("tree", [{"truncated": True, "tree": []}, {"tree": [
    {"path": "app/page.tsx", "type": "blob", "mode": "120000", "sha": BASE, "size": 10}]},
    {"tree": [{"path": "../app/page.tsx", "type": "blob", "mode": "100644", "sha": BASE, "size": 10}]},
    {"tree": [{"path": "app/page.tsx", "type": "blob", "mode": "100644", "sha": BASE, "size": 200000}]}])
async def test_unsupported_source_trees_are_rejected(make_client, tree):
    client, _ = make_client({("GET", f"/repos/owner/site/git/trees/{BASE}"): tree})
    with pytest.raises(GitHubError):
        await client.sources(REPO, BASE)


async def test_source_blob_digest_must_match_frozen_tree(make_client):
    client, _ = make_client({
        ("GET", f"/repos/owner/site/git/trees/{BASE}"): {"tree": [
            {"path": "app/page.tsx", "type": "blob", "mode": "100644", "sha": BASE, "size": 20}]},
        ("GET", f"/repos/owner/site/git/blobs/{BASE}"): {
            "sha": BASE, "encoding": "base64", "content": base64.b64encode(b"wrong content").decode()},
    })
    with pytest.raises(GitHubError) as failure:
        await client.sources(REPO, BASE)
    assert failure.value.code == "unsupported"


async def test_branch_head_and_atomic_commit_expected_oid(make_client):
    client, seen = make_client({
        ("GET", "/repos/owner/site/git/ref/heads/main"): {"object": {"type": "commit", "sha": BASE}},
        ("POST", "/repos/owner/site/git/refs"): {"ref": "refs/heads/seopilot/fix"},
        ("POST", "/graphql"): {"data": {"createCommitOnBranch": {"commit": {"oid": HEAD}}}},
    })
    assert await client.head(REPO, "main") == BASE
    assert await client.branch_head(REPO, "seopilot/missing") is None
    await client.create_branch(REPO, "seopilot/fix", BASE)
    assert await client.commit(REPO, "seopilot/fix", BASE, {"web/app/page.tsx": "source"}, "Update metadata") == HEAD
    mutation = json.loads(next(request.content for request in seen if request.url.path == "/graphql"))
    assert mutation["variables"]["input"]["expectedHeadOid"] == BASE
    assert mutation["variables"]["input"]["fileChanges"] == {
        "additions": [{"path": "web/app/page.tsx", "contents": base64.b64encode(b"source").decode()}]}
    assert "force" not in json.dumps(mutation)


@pytest.mark.parametrize("path", ["app/layout.tsx", ".github/workflows/run.yml", "package.json", "../app/page.tsx"])
async def test_forbidden_file_edits_are_rejected_before_write(make_client, path):
    client, seen = make_client()
    with pytest.raises(GitHubError):
        await client.commit(REPO, "seopilot/fix", BASE, {path: "malicious"}, "Metadata")
    assert not any(request.url.path == "/graphql" for request in seen)


@pytest.mark.parametrize("branch", ["main", "other/fix", "seopilot/../main", "seopilot/a.lock", "seopilot/x\nmain"])
async def test_branch_mutations_never_write_default_or_unsafe_branches(make_client, branch):
    client, seen = make_client()
    with pytest.raises(GitHubError):
        await client.create_branch(REPO, branch, BASE)
    assert not any(request.url.path.endswith("/git/refs") for request in seen)


async def test_uncertain_writes_are_never_automatically_retried(make_client):
    client, seen = make_client({("POST", "/repos/owner/site/git/refs"):
                              httpx.ReadTimeout("secret signed URL and private content must not leak")})
    with pytest.raises(GitHubError) as failure:
        await client.create_branch(REPO, "seopilot/fix", BASE)
    assert failure.value.code == "uncertain" and "secret" not in str(failure.value)
    assert len([request for request in seen if request.url.path.endswith("/git/refs")]) == 1


@pytest.mark.parametrize("response", [httpx.Response(502, text="private-response-canary"),
                                       httpx.Response(201, text="not JSON private-response-canary")])
async def test_server_or_invalid_write_responses_require_reconciliation(make_client, response):
    client, _ = make_client({("POST", "/repos/owner/site/git/refs"): response})
    with pytest.raises(GitHubError) as failure:
        await client.create_branch(REPO, "seopilot/fix", BASE)
    assert failure.value.code == "uncertain" and "canary" not in str(failure.value)


@pytest.mark.parametrize("mode", ["exact", "extra", "different_parent", "merge", "wrong_blob", "rename", "duplicate"])
async def test_uncertain_commit_reconciliation_verifies_parent_and_exact_file_set(make_client, mode):
    content = 'export const metadata = { title: "Café" };'
    blob_sha, _ = blob(content)
    changed = [{"filename": "app/page.tsx", "status": "modified", "sha": blob_sha}]
    parents = [{"sha": BASE}]
    if mode == "extra":
        changed.append({"filename": "package.json", "status": "modified", "sha": blob_sha})
    if mode == "different_parent":
        parents[0]["sha"] = "c" * 40
    if mode == "merge":
        parents.append({"sha": "c" * 40})
    if mode == "wrong_blob":
        changed[0]["sha"] = BASE
    if mode == "rename":
        changed[0]["status"] = "renamed"
    if mode == "duplicate":
        changed.append(dict(changed[0]))
    client, _ = make_client({("GET", f"/repos/owner/site/commits/{HEAD}"):
                            {"sha": HEAD, "parents": parents, "files": changed}})
    assert await client.verify_commit(REPO, HEAD, BASE, {"app/page.tsx": content}) is (mode == "exact")


async def test_draft_pull_requests_have_strict_identity(make_client):
    client, seen = make_client({("POST", "/repos/owner/site/pulls"): pull(),
                                ("GET", "/repos/owner/site/pulls"): [pull()],
                                ("GET", "/repos/owner/site/pulls/4"): pull(merged_at=NOW.isoformat(), state="closed")})
    result = await client.create_pull_request(REPO, "seopilot/fix", "main", "Metadata", "Approved diff")
    assert result["url"] == "https://github.com/owner/site/pull/4" and result["draft"]
    body = json.loads(next(request.content for request in seen if request.url.path.endswith("/pulls")))
    assert body["draft"] and not body["maintainer_can_modify"]
    assert (await client.find_pull_request(REPO, "seopilot/fix"))["head_sha"] == HEAD
    assert (await client.get_pull_request(REPO, 4))["merged"]


@pytest.mark.parametrize("response", [pull(draft=False), pull(head={"repo": {"id": 99}, "ref": "seopilot/fix", "sha": HEAD})])
async def test_non_draft_or_wrong_repository_pr_is_rejected(make_client, response):
    client, _ = make_client({("POST", "/repos/owner/site/pulls"): response})
    with pytest.raises(GitHubError):
        await client.create_pull_request(REPO, "seopilot/fix", "main", "Metadata", "Approved diff")


def validation_routes(run):
    return {("GET", "/repos/owner/site/actions/workflows/seopilot-validation.yml"):
                {"id": 42, "path": ".github/workflows/seopilot-validation.yml"},
            ("GET", "/repos/owner/site/actions/workflows/42/runs"): {"workflow_runs": [run]},
            ("GET", "/repos/owner/site/actions/runs/101/artifacts"): {"total_count": 3, "artifacts": [
                {"id": 5, "name": "seopilot-validation", "size_in_bytes": 500, "expired": False},
                {"id": 6, "name": "expired", "size_in_bytes": 500, "expired": True},
                {"id": 7, "name": "huge", "size_in_bytes": MAX_ARTIFACT + 1, "expired": False}]}}


def workflow_run(**updates):
    return {"id": 101, "workflow_id": 42, "path": ".github/workflows/seopilot-validation.yml",
            "head_sha": HEAD, "event": "pull_request", "head_repository": {"id": 7},
            "status": "completed", "conclusion": "failure", **updates}


async def test_validation_reports_ci_failure_and_matching_bounded_artifacts(make_client):
    client, _ = make_client(validation_routes(workflow_run()))
    result = await client.validation(REPO, "seopilot-validation.yml", HEAD)
    assert result["conclusion"] == "failure" and result["status"] == "completed"
    assert result["path"] == ".github/workflows/seopilot-validation.yml" and result["head_sha"] == HEAD
    assert result["artifacts"] == [{"id": 5, "name": "seopilot-validation", "size_in_bytes": 500, "expired": False}]


@pytest.mark.parametrize("updates", [{"head_sha": BASE}, {"workflow_id": 999}, {"event": "pull_request_target"},
    {"path": ".github/workflows/other.yml"}, {"head_repository": {"id": 999}}])
async def test_validation_does_not_trust_wrong_workflow_sha_event_or_fork(make_client, updates):
    client, _ = make_client(validation_routes(workflow_run(**updates)))
    result = await client.validation(REPO, "seopilot-validation.yml", HEAD)
    assert result["status"] == "pending" and not result["artifacts"]


async def test_artifact_redirect_never_forwards_bearer_and_bounds_storage(make_client):
    download = "https://example.blob.core.windows.net/artifact?signature=private-canary"
    routes = {("GET", "/repos/owner/site/actions/artifacts/5"):
                {"id": 5, "expired": False, "size_in_bytes": 3},
              ("GET", "/repos/owner/site/actions/artifacts/5/zip"):
                httpx.Response(302, headers={"location": download}),
              ("GET", "/artifact"): httpx.Response(200, content=b"zip")}
    client, seen = make_client(routes)
    assert await client.artifact_bytes(REPO, 5) == b"zip"
    redirected = seen[-1]
    assert redirected.url.host == "example.blob.core.windows.net"
    assert not redirected.headers.get("authorization")


@pytest.mark.parametrize("location", ["http://example.blob.core.windows.net/x", "https://evil.test/x",
    "https://user:password@example.blob.core.windows.net/x", "https://example.blob.core.windows.net:8443/x"])
async def test_artifact_rejects_unsafe_redirect_locations(make_client, location):
    client, seen = make_client({
        ("GET", "/repos/owner/site/actions/artifacts/5"): {"id": 5, "expired": False, "size_in_bytes": 3},
        ("GET", "/repos/owner/site/actions/artifacts/5/zip"): httpx.Response(302, headers={"location": location})})
    with pytest.raises(GitHubError) as failure:
        await client.artifact_bytes(REPO, 5)
    assert failure.value.code == "invalid_response"
    assert all(request.url.host == "api.github.com" for request in seen)


@pytest.mark.parametrize("metadata", [{"id": 5, "expired": True, "size_in_bytes": 3},
    {"id": 6, "expired": False, "size_in_bytes": 3},
    {"id": 5, "expired": False, "size_in_bytes": MAX_ARTIFACT + 1}])
async def test_artifact_rejects_expired_forged_or_oversized_metadata(make_client, metadata):
    client, seen = make_client({("GET", "/repos/owner/site/actions/artifacts/5"): metadata})
    with pytest.raises(GitHubError):
        await client.artifact_bytes(REPO, 5)
    assert not any(request.url.path.endswith("/zip") for request in seen)


async def test_json_and_artifact_body_limits_apply_to_actual_bytes(make_client):
    client, _ = make_client({("GET", "/app/installations/3"):
                            httpx.Response(200, content=b"x" * (2 * 1024 * 1024 + 1))})
    with pytest.raises(GitHubError) as failure:
        await client.authorize(3, 7)
    assert failure.value.code == "limit"
    client, _ = make_client({
        ("GET", "/repos/owner/site/actions/artifacts/5"): {"id": 5, "expired": False, "size_in_bytes": 3},
        ("GET", "/repos/owner/site/actions/artifacts/5/zip"):
            httpx.Response(200, content=b"x" * (MAX_ARTIFACT + 1))})
    with pytest.raises(GitHubError) as failure:
        await client.artifact_bytes(REPO, 5)
    assert failure.value.code == "limit"
