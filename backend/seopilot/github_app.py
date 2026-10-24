"""Bounded GitHub App access. Repository content never crosses an AI boundary."""

import base64
import hashlib
import json
import logging
import os
import re
import ssl
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Callable
from urllib.parse import quote, urlsplit

import httpx
import jwt

API = "https://api.github.com"
API_VERSION = "2026-03-10"
MAX_JSON = 2 * 1024 * 1024
MAX_ARTIFACT = 4 * 1024 * 1024
MAX_SOURCES = 1024 * 1024
OWNER = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}\Z")
NAME = re.compile(r"[A-Za-z0-9_.-]{1,100}\Z")
SHA = re.compile(r"[a-f0-9]{40}\Z")
PERMISSIONS = {"metadata": "read", "contents": "write", "pull_requests": "write", "actions": "read"}


class GitHubError(Exception):
    """Only fixed, sanitized messages may leave the provider boundary."""

    def __init__(self, message: str, code: str = "unavailable"):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class GithubConfig:
    app_id: int | None = None
    private_key_path: Path | None = field(default=None, repr=False)
    owners: tuple[str, ...] = ()

    @property
    def configured(self) -> bool:
        return bool(self.app_id and self.private_key_path and self.owners)

    @classmethod
    def from_env(cls):
        raw_id = os.environ.get("GITHUB_APP_ID", "").strip()
        raw_path = os.environ.get("GITHUB_APP_PRIVATE_KEY_PATH", "").strip()
        owners = tuple(dict.fromkeys(item.strip().lower() for item in
                                     os.environ.get("GITHUB_APP_OWNERS", "").split(",") if item.strip()))
        if raw_id and (not raw_id.isdecimal() or int(raw_id) <= 0):
            raise ValueError("GITHUB_APP_ID must be a positive integer")
        if any(not OWNER.fullmatch(owner) for owner in owners):
            raise ValueError("GITHUB_APP_OWNERS must contain GitHub owner names")
        path = Path(raw_path).expanduser() if raw_path else None
        if path and not path.is_absolute():
            path = Path(__file__).resolve().parents[1] / path
        return cls(int(raw_id) if raw_id else None, path, owners)


@dataclass(frozen=True)
class Repository:
    id: int
    installation_id: int
    owner: str
    name: str
    default_branch: str
    node_id: str


@dataclass
class _Token:
    value: str = field(repr=False)
    expires: datetime


def _positive(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _sha(value: str) -> str:
    if not isinstance(value, str) or not SHA.fullmatch(value):
        raise GitHubError("A full Git commit SHA is required.", "invalid")
    return value


def _branch(value: str) -> str:
    if (not isinstance(value, str) or not 1 <= len(value) <= 200 or value.startswith(("/", ".", "-"))
            or value.endswith(("/", ".", ".lock")) or ".." in value or "@{" in value
            or any(char.isspace() or char in "~^:?*[\\\x00" for char in value)
            or any(not part or part.startswith(".") or part.endswith(".lock") for part in value.split("/"))):
        raise GitHubError("The repository branch name is invalid.", "invalid")
    return value


def _path(value: str, *, empty: bool = False) -> str:
    if empty and value == "":
        return value
    if (not isinstance(value, str) or len(value) > 500 or "\\" in value or "\x00" in value
            or value.startswith("/") or any(part in {"", ".", "..", ".git"} for part in value.split("/"))):
        raise GitHubError("The repository path is invalid.", "invalid")
    return value


class GitHubClient:
    def __init__(self, config: GithubConfig, *, client: httpx.AsyncClient | None = None,
                 clock: Callable[[], datetime] | None = None):
        self.config = config
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            trust_env=False, verify=ssl.create_default_context(), follow_redirects=False,
            timeout=httpx.Timeout(20, connect=5), limits=httpx.Limits(max_connections=4),
        )
        self._clock = clock or (lambda: datetime.now(UTC))
        self._tokens: dict[tuple[int, int | None], _Token] = {}
        # HTTP debug logs can include signed artifact URLs and private GitHub response headers.
        for name in ("httpx", "httpcore"):
            logging.getLogger(name).setLevel(logging.WARNING)

    def status(self) -> dict:
        return {"configured": self.config.configured, "owners": list(self.config.owners),
                "message": "GitHub App configured; connect an installed repository."
                if self.config.configured else "Configure the server-side GitHub App to connect a repository."}

    async def close(self):
        self._tokens.clear()
        if self._owns_client:
            await self._client.aclose()

    def forget(self):
        """Disconnect clears in-memory installation credentials immediately."""
        self._tokens.clear()

    def _jwt(self) -> str:
        if not self.config.configured:
            raise GitHubError("GitHub App setup is incomplete.", "not_configured")
        try:
            path = self.config.private_key_path
            if path is None or path.stat().st_size > 65536:
                raise ValueError()
            key = path.read_bytes()
            now = int(self._clock().timestamp())
            return jwt.encode({"iat": now - 60, "exp": now + 540, "iss": str(self.config.app_id)},
                              key, algorithm="RS256")
        except (OSError, ValueError, TypeError, jwt.PyJWTError):
            raise GitHubError("The server-side GitHub App private key could not be used.", "credentials") from None

    async def _response(self, method: str, path: str, *, token: str, data=None,
                        params=None, limit: int = MAX_JSON, allow_redirect: bool = False):
        if not path.startswith("/") or path.startswith("//"):
            raise GitHubError("Invalid GitHub API request.", "invalid")
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                   "X-GitHub-Api-Version": API_VERSION, "User-Agent": "SEOPilot-local"}
        try:
            async with self._client.stream(method, API + path, headers=headers, json=data,
                                           params=params, follow_redirects=False) as response:
                if response.status_code == 302 and allow_redirect:
                    return response.status_code, response.headers, b""
                if response.status_code >= 300:
                    if response.status_code == 401:
                        self._tokens.clear()
                    errors = {401: ("GitHub credentials expired or were revoked.", "credentials"),
                              403: ("GitHub denied access or its request limit was reached.", "forbidden"),
                              404: ("The GitHub resource is unavailable or access was revoked.", "not_found"),
                              409: ("The repository changed; recreate the proposal.", "conflict"),
                              422: ("GitHub rejected the requested repository change.", "conflict"),
                              429: ("GitHub's request limit was reached; try again later.", "limited")}
                    fallback = ("GitHub could not complete the request.", "unavailable")
                    if response.status_code >= 500 and method not in {"GET", "HEAD"}:
                        fallback = ("GitHub's write outcome is uncertain; reconcile before retrying.", "uncertain")
                    message, code = errors.get(response.status_code, fallback)
                    raise GitHubError(message, code)
                content = bytearray()
                async for chunk in response.aiter_bytes():
                    content.extend(chunk)
                    if len(content) > limit:
                        raise GitHubError("GitHub returned more data than this operation permits.", "limit")
                return response.status_code, response.headers, bytes(content)
        except (httpx.HTTPError, OSError):
            code = "uncertain" if method not in {"GET", "HEAD"} else "unavailable"
            message = "GitHub's write outcome is uncertain; reconcile before retrying." if code == "uncertain" else (
                "GitHub is temporarily unreachable.")
            raise GitHubError(message, code) from None

    async def _json(self, method: str, path: str, *, token: str, data=None, params=None):
        _, _, content = await self._response(method, path, token=token, data=data, params=params)
        try:
            value = json.loads(content)
            if not isinstance(value, (dict, list)):
                raise ValueError()
            return value
        except (ValueError, UnicodeError):
            code = "invalid_response" if method in {"GET", "HEAD"} else "uncertain"
            raise GitHubError("GitHub returned an invalid response; reconcile any pending write.", code) from None

    async def _installation(self, installation_id: int) -> dict:
        if not _positive(installation_id):
            raise GitHubError("The GitHub installation ID is invalid.", "invalid")
        item = await self._json("GET", f"/app/installations/{installation_id}", token=self._jwt())
        if not isinstance(item, dict):
            raise GitHubError("GitHub returned an invalid installation.", "invalid_response")
        owner = item.get("account", {}).get("login", "")
        permissions = item.get("permissions", {})
        if (item.get("id") != installation_id or not isinstance(owner, str)
                or owner.lower() not in self.config.owners or item.get("suspended_at")
                or item.get("app_id", self.config.app_id) != self.config.app_id
                or item.get("repository_selection") != "selected"
                or not isinstance(permissions, dict)
                or any(name not in PERMISSIONS or grant != PERMISSIONS[name]
                       for name, grant in permissions.items())):
            raise GitHubError("This GitHub installation is not authorized.", "forbidden")
        return item

    async def _token(self, installation_id: int, repository_id: int | None = None) -> str:
        key = (installation_id, repository_id)
        cached = self._tokens.get(key)
        if cached and cached.expires > self._clock() + timedelta(seconds=60):
            return cached.value
        body = {"permissions": PERMISSIONS if repository_id else {"metadata": "read"}}
        if repository_id:
            body["repository_ids"] = [repository_id]
        result = await self._json("POST", f"/app/installations/{installation_id}/access_tokens",
                                  token=self._jwt(), data=body)
        try:
            value = result["token"]
            expires = datetime.fromisoformat(result["expires_at"].replace("Z", "+00:00"))
            if (not isinstance(value, str) or not 1 <= len(value) <= 20000
                    or any(not 33 <= ord(char) <= 126 for char in value) or expires.tzinfo is None
                    or expires <= self._clock()):
                raise ValueError()
            # A narrowed token must not grant permissions outside the App's documented scope.
            if any(name not in PERMISSIONS or PERMISSIONS[name] != grant
                   for name, grant in result.get("permissions", {}).items()):
                raise ValueError()
        except (KeyError, TypeError, ValueError, AttributeError):
            raise GitHubError("GitHub returned an invalid installation credential.", "credentials") from None
        self._tokens[key] = _Token(value, expires)
        return value

    def _repository(self, item: dict, installation_id: int, owner: str) -> Repository:
        try:
            login = item["owner"]["login"]
            if (not _positive(item["id"]) or not isinstance(login, str) or login.lower() != owner.lower()
                    or login.lower() not in self.config.owners or not OWNER.fullmatch(login)
                    or not NAME.fullmatch(item["name"]) or item.get("archived") or item.get("disabled")):
                raise ValueError()
            return Repository(item["id"], installation_id, login, item["name"],
                              _branch(item["default_branch"]), str(item["node_id"]))
        except (KeyError, TypeError, ValueError, AttributeError):
            raise GitHubError("GitHub returned an unsupported or unauthorized repository.", "forbidden") from None

    async def list_repositories(self) -> list[Repository]:
        installations = []
        for page in range(1, 11):
            items = await self._json("GET", "/app/installations", token=self._jwt(),
                                     params={"per_page": 100, "page": page})
            if not isinstance(items, list):
                raise GitHubError("GitHub returned an invalid installation list.", "invalid_response")
            installations.extend(items)
            if len(items) < 100:
                break
        else:
            raise GitHubError("Too many GitHub installations; narrow the App's access.", "limit")
        repositories = []
        allowed = [item for item in installations if isinstance(item, dict)
                   and item.get("account", {}).get("login", "").lower() in self.config.owners]
        if len(allowed) > 10:
            raise GitHubError("Too many allowed installations; narrow the App's access.", "limit")
        for item in allowed:
            owner = item.get("account", {}).get("login", "")
            if not isinstance(owner, str) or owner.lower() not in self.config.owners or item.get("suspended_at"):
                continue
            installation = await self._installation(item.get("id"))
            token = await self._token(installation["id"])
            for page in range(1, 11):
                result = await self._json("GET", "/installation/repositories", token=token,
                                          params={"per_page": 100, "page": page})
                values = result.get("repositories", [])
                if not isinstance(values, list):
                    raise GitHubError("GitHub returned an invalid repository list.", "invalid_response")
                repositories.extend(self._repository(repo, installation["id"], owner) for repo in values
                                    if isinstance(repo, dict) and not repo.get("archived") and not repo.get("disabled"))
                if len(repositories) > 1000:
                    raise GitHubError("Too many repositories; select fewer repositories for the App.", "limit")
                if len(values) < 100:
                    break
            else:
                raise GitHubError("Too many repositories; select fewer repositories for the App.", "limit")
        return repositories

    async def authorize(self, installation_id: int, repository_id: int) -> Repository:
        if not _positive(repository_id):
            raise GitHubError("The GitHub repository ID is invalid.", "invalid")
        installation = await self._installation(installation_id)
        token = await self._token(installation_id, repository_id)
        item = await self._json("GET", f"/repositories/{repository_id}", token=token)
        repo = self._repository(item, installation_id, installation["account"]["login"])
        if repo.id != repository_id:
            raise GitHubError("The GitHub repository identity changed.", "forbidden")
        return repo

    async def _access(self, repo: Repository) -> tuple[str, str]:
        current = await self.authorize(repo.installation_id, repo.id)
        if current != repo:
            raise GitHubError("The repository identity changed; reconnect the project.", "conflict")
        return f"/repos/{quote(repo.owner, safe='')}/{quote(repo.name, safe='')}", await self._token(
            repo.installation_id, repo.id)

    async def head(self, repo: Repository, branch: str) -> str:
        prefix, token = await self._access(repo)
        item = await self._json("GET", prefix + "/git/ref/heads/" + quote(_branch(branch), safe=""), token=token)
        if item.get("object", {}).get("type") != "commit":
            raise GitHubError("The repository ref does not point to a commit.", "conflict")
        return _sha(item["object"]["sha"])

    async def branch_head(self, repo: Repository, branch: str) -> str | None:
        try:
            return await self.head(repo, branch)
        except GitHubError as error:
            if error.code == "not_found":
                return None
            raise

    async def sources(self, repo: Repository, sha: str, app_subdir: str = "") -> dict[str, str]:
        prefix, token = await self._access(repo)
        app_subdir = _path(app_subdir, empty=True)
        root = app_subdir + "/" if app_subdir else ""
        tree = await self._json("GET", prefix + "/git/trees/" + _sha(sha), token=token,
                                params={"recursive": "1"})
        entries = tree.get("tree", [])
        if tree.get("truncated") or not isinstance(entries, list) or len(entries) > 1000:
            raise GitHubError("The repository tree exceeds the supported source limit.", "limit")
        paths = []
        for entry in entries:
            path = _path(entry.get("path", ""))
            local = path.removeprefix(root) if path.startswith(root) else ""
            router = local.startswith(("app/", "src/app/"))
            if router and entry.get("mode") == "120000":
                raise GitHubError("Symlinked App Router sources are unsupported.", "unsupported")
            if entry.get("type") != "blob" or not local:
                continue
            source = router and PurePosixPath(local).name in {
                stem + suffix for stem in ("page", "layout") for suffix in (".ts", ".tsx", ".js", ".jsx")}
            if source or local == "package.json":
                if entry.get("mode") not in {"100644", "100755"} or entry.get("size", MAX_SOURCES) > 128 * 1024:
                    raise GitHubError("An App Router source file is unsupported or too large.", "limit")
                paths.append((path, _sha(entry.get("sha", ""))))
        if len(paths) > 100:
            raise GitHubError("Too many App Router source files; select a smaller application.", "limit")
        sources, total = {}, 0
        for path, blob_sha in paths:
            blob = await self._json("GET", prefix + "/git/blobs/" + blob_sha, token=token)
            try:
                if blob.get("encoding") != "base64" or blob.get("sha") != blob_sha:
                    raise ValueError()
                raw = base64.b64decode(blob["content"].replace("\n", ""), validate=True)
                if len(raw) > 128 * 1024:
                    raise ValueError()
                digest = hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()
                if digest != blob_sha:
                    raise ValueError()
                total += len(raw)
                if total > MAX_SOURCES:
                    raise GitHubError("The App Router source budget was exceeded.", "limit")
                sources[path] = raw.decode("utf-8")
            except (KeyError, TypeError, ValueError, UnicodeError):
                raise GitHubError("An App Router source file is invalid or unsupported.", "unsupported") from None
        return sources

    async def create_branch(self, repo: Repository, branch: str, base_sha: str):
        prefix, token = await self._access(repo)
        branch = _branch(branch)
        if not branch.startswith("seopilot/") or branch == repo.default_branch:
            raise GitHubError("SEOPilot may write only its dedicated fix branches.", "forbidden")
        await self._json("POST", prefix + "/git/refs", token=token,
                         data={"ref": "refs/heads/" + branch, "sha": _sha(base_sha)})

    async def commit(self, repo: Repository, branch: str, expected_head: str, files: dict[str, str], message: str) -> str:
        _, token = await self._access(repo)
        if not _branch(branch).startswith("seopilot/") or branch == repo.default_branch:
            raise GitHubError("SEOPilot may write only its dedicated fix branches.", "forbidden")
        if not 1 <= len(files) <= 5 or not 1 <= len(message) <= 200:
            raise GitHubError("The commit exceeds the supported change limits.", "limit")
        additions = []
        for path, value in files.items():
            path = _path(path)
            if (PurePosixPath(path).name not in {"page.ts", "page.tsx", "page.js", "page.jsx"}
                    or not any(path.startswith(root) or "/" + root in path for root in ("app/", "src/app/"))
                    or not isinstance(value, str) or len(value.encode("utf-8")) > 128 * 1024):
                raise GitHubError("Only supported page metadata files can be committed.", "forbidden")
            additions.append({"path": path, "contents": base64.b64encode(value.encode("utf-8")).decode("ascii")})
        result = await self._json("POST", "/graphql", token=token, data={
            "query": "mutation($input:CreateCommitOnBranchInput!){createCommitOnBranch(input:$input){commit{oid}}}",
            "variables": {"input": {"branch": {"repositoryNameWithOwner": f"{repo.owner}/{repo.name}",
                                                 "branchName": branch},
                                       "expectedHeadOid": _sha(expected_head), "message": {"headline": message},
                                       "fileChanges": {"additions": additions}}}})
        if result.get("errors"):
            raise GitHubError("GitHub rejected the commit; check the branch before retrying.", "conflict")
        try:
            return _sha(result["data"]["createCommitOnBranch"]["commit"]["oid"])
        except (KeyError, TypeError):
            raise GitHubError("The commit outcome is uncertain; reconcile before retrying.", "uncertain") from None

    async def verify_commit(self, repo: Repository, sha: str, base_sha: str, files: dict[str, str]) -> bool:
        """Reconcile an uncertain write without trusting only the branch name or latest file text."""
        if not 1 <= len(files) <= 5:
            return False
        prefix, token = await self._access(repo)
        result = await self._json("GET", prefix + "/commits/" + _sha(sha), token=token,
                                  params={"per_page": 100})
        expected = {}
        for path, content in files.items():
            path = _path(path)
            raw = content.encode("utf-8")
            expected[path] = hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()
        changed = result.get("files", [])
        parents = result.get("parents", [])
        if (result.get("sha") != sha or not isinstance(parents, list) or len(parents) != 1
                or parents[0].get("sha") != _sha(base_sha)
                or not isinstance(changed, list) or len(changed) != len(expected)):
            return False
        actual = {}
        for item in changed:
            if not isinstance(item, dict) or item.get("status") not in {"added", "modified"}:
                return False
            path = item.get("filename")
            if path not in expected or path in actual:
                return False
            actual[path] = item.get("sha")
        return actual == expected

    async def find_pull_request(self, repo: Repository, branch: str) -> dict | None:
        prefix, token = await self._access(repo)
        values = await self._json("GET", prefix + "/pulls", token=token,
                                  params={"head": repo.owner + ":" + _branch(branch), "state": "all", "per_page": 10})
        if not isinstance(values, list) or len(values) > 1:
            raise GitHubError("The fix branch has ambiguous pull request history.", "conflict")
        return self._pull(values[0], repo, branch) if values else None

    def _pull(self, item: dict, repo: Repository, branch: str | None = None) -> dict:
        try:
            if (not _positive(item["number"]) or item["head"]["repo"]["id"] != repo.id
                    or item["base"]["repo"]["id"] != repo.id
                    or (branch and item["head"]["ref"] != branch)):
                raise ValueError()
            sha = _sha(item["head"]["sha"])
            url = f"https://github.com/{repo.owner}/{repo.name}/pull/{item['number']}"
            return {"number": item["number"], "url": url, "html_url": url,
                    "head": {"sha": sha, "ref": item["head"]["ref"]}, "base": {"ref": item["base"]["ref"]},
                    "head_sha": sha, "head_branch": item["head"]["ref"],
                    "base_branch": item["base"]["ref"], "draft": bool(item.get("draft")),
                    "state": item["state"], "merged": bool(item.get("merged_at") or item.get("merged")),
                    "merged_at": item.get("merged_at")}
        except (KeyError, TypeError, ValueError):
            raise GitHubError("GitHub returned an invalid pull request identity.", "conflict") from None

    async def create_pull_request(self, repo: Repository, branch: str, base: str, title: str, body: str) -> dict:
        prefix, token = await self._access(repo)
        if (not _branch(branch).startswith("seopilot/") or branch == repo.default_branch
                or _branch(base) == branch or not 1 <= len(title) <= 200 or len(body.encode("utf-8")) > 16000):
            raise GitHubError("The draft pull request request is invalid.", "invalid")
        item = await self._json("POST", prefix + "/pulls", token=token,
                                data={"head": branch, "base": base, "title": title, "body": body,
                                      "draft": True, "maintainer_can_modify": False})
        result = self._pull(item, repo, branch)
        if not result["draft"]:
            raise GitHubError("GitHub did not create the required draft pull request.", "conflict")
        return result

    async def get_pull_request(self, repo: Repository, number: int) -> dict:
        if not _positive(number):
            raise GitHubError("The pull request number is invalid.", "invalid")
        prefix, token = await self._access(repo)
        item = await self._json("GET", prefix + f"/pulls/{number}", token=token)
        return self._pull(item, repo)

    async def validation(self, repo: Repository, workflow: str, sha: str) -> dict:
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}\.ya?ml", workflow):
            raise GitHubError("The validation workflow filename is invalid.", "invalid")
        prefix, token = await self._access(repo)
        sha = _sha(sha)
        configured = await self._json("GET", prefix + "/actions/workflows/" + quote(workflow, safe=""), token=token)
        path = ".github/workflows/" + workflow
        if configured.get("path") != path or not _positive(configured.get("id")):
            raise GitHubError("The configured validation workflow identity did not match.", "conflict")
        values = await self._json("GET", prefix + f"/actions/workflows/{configured['id']}/runs", token=token,
                                  params={"head_sha": sha, "event": "pull_request", "per_page": 20})
        runs = values.get("workflow_runs", [])
        if not isinstance(runs, list) or len(runs) > 20:
            raise GitHubError("GitHub returned an invalid validation run list.", "invalid_response")
        result = {"status": "pending", "run_id": None, "workflow_id": configured["id"], "html_url": None,
                  "path": path, "head_sha": sha, "conclusion": None, "artifacts": []}
        for run in runs:
            if (run.get("workflow_id") != configured["id"] or run.get("path") != path
                    or run.get("head_sha") != sha or run.get("event") != "pull_request"
                    or run.get("head_repository", {}).get("id") != repo.id):
                continue
            if not _positive(run.get("id")):
                raise GitHubError("GitHub returned an invalid validation run.", "invalid_response")
            result.update(status=run.get("status"), run_id=run["id"], conclusion=run.get("conclusion"),
                          html_url=f"https://github.com/{repo.owner}/{repo.name}/actions/runs/{run['id']}")
            if result["status"] == "completed":
                listing = await self._json("GET", prefix + f"/actions/runs/{run['id']}/artifacts", token=token,
                                           params={"per_page": 100})
                artifacts = listing.get("artifacts", [])
                if listing.get("total_count", 0) > 100 or not isinstance(artifacts, list):
                    raise GitHubError("Validation artifacts exceed the supported limit.", "limit")
                for artifact in artifacts:
                    if (not artifact.get("expired") and _positive(artifact.get("id"))
                            and isinstance(artifact.get("size_in_bytes"), int)
                            and 0 < artifact["size_in_bytes"] <= MAX_ARTIFACT
                            and isinstance(artifact.get("name"), str) and len(artifact["name"]) <= 200):
                        result["artifacts"].append({**{key: artifact[key] for key in ("id", "name", "size_in_bytes")},
                                                    "expired": False})
            break
        return result

    async def artifact_bytes(self, repo: Repository, artifact_id: int) -> bytes:
        if not _positive(artifact_id):
            raise GitHubError("The validation artifact ID is invalid.", "invalid")
        prefix, token = await self._access(repo)
        metadata = await self._json("GET", prefix + f"/actions/artifacts/{artifact_id}", token=token)
        if (metadata.get("id") != artifact_id or metadata.get("expired")
                or not isinstance(metadata.get("size_in_bytes"), int)
                or not 0 < metadata["size_in_bytes"] <= MAX_ARTIFACT):
            raise GitHubError("The validation artifact is expired or exceeds its size limit.", "limit")
        status, headers, content = await self._response("GET", prefix + f"/actions/artifacts/{artifact_id}/zip",
                                                        token=token, limit=MAX_ARTIFACT, allow_redirect=True)
        if status != 302:
            return content
        location = headers.get("location", "")
        try:
            target = urlsplit(location)
            port = target.port
        except ValueError:
            raise GitHubError("GitHub returned an unsupported artifact download location.", "invalid_response") from None
        host = target.hostname or ""
        if (target.scheme != "https" or target.username or target.password or port not in {None, 443}
                or target.fragment or not any(host.endswith("." + domain)
                                              for domain in ("blob.core.windows.net", "actions.githubusercontent.com"))):
            raise GitHubError("GitHub returned an unsupported artifact download location.", "invalid_response")
        try:
            # This is a signed storage URL. Never forward installation credentials to it.
            async with self._client.stream("GET", location, headers={"Authorization": ""},
                                           follow_redirects=False) as response:
                if response.status_code != 200:
                    raise GitHubError("The validation artifact could not be downloaded.", "unavailable")
                content = bytearray()
                async for chunk in response.aiter_bytes():
                    content.extend(chunk)
                    if len(content) > MAX_ARTIFACT:
                        raise GitHubError("The validation artifact exceeds its size limit.", "limit")
                return bytes(content)
        except (httpx.HTTPError, OSError):
            raise GitHubError("The validation artifact could not be downloaded.", "unavailable") from None
