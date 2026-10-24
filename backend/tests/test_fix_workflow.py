"""Exercise the owned-repository workflow with fresh databases and zero live credentials."""

import asyncio
import copy
import io
import json
import threading
import zipfile
from contextlib import contextmanager
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from seopilot.app import create_app
from seopilot.fix_engine import compare_live
from seopilot.fix_models import FixRun, FixTarget
from seopilot.github_app import GitHubError, Repository
from seopilot.models import Audit, Coverage, Evidence, Issue, Page, Recommendation, Score
from seopilot.settings import Settings

ORIGIN = "https://example.org"
URL = ORIGIN + "/"
BASE = "a" * 40
CANARY = "PRIVATE_REPOSITORY_SOURCE_MUST_NEVER_REACH_AI"
OLD_TITLE = "Existing page title"
OLD_DESCRIPTION = "An existing description that must remain intact unless explicitly changed."
TITLE = "Reviewed page title for the owned pilot website"
DESCRIPTION = "A reviewed description explaining the owned pilot website accurately and clearly."


class FakeGitHub:
    """Fake remote keeps writes after a lost response, just as GitHub may do."""

    def __init__(self):
        self.repo = Repository(7, 3, "owner", "site", "main", "R_7")
        self.branches = {"main": BASE}
        self.snapshots = {BASE: {
            "package.json": '{"dependencies":{"next":"16.4.3"}}',
            "app/layout.tsx": 'export default function Layout({children}: {children: React.ReactNode}) { return <html><body>{children}</body></html>; }\n',
            "app/page.tsx": f'// {CANARY}\nexport const metadata = {{ title: {json.dumps(OLD_TITLE)}, description: {json.dumps(OLD_DESCRIPTION)} }};\nexport default function Page() {{ return <main>Owned pilot site with meaningful content for visitors.</main>; }}\n',
        }}
        self.parents = {}
        self.changed = {}
        self.pulls = {}
        self.counts = {"branch": 0, "commit": 0, "pr": 0, "authorize": 0}
        self.lose_once = None
        self.revoked = False
        self.closed = False
        self.checks = {"status": "pending", "conclusion": None, "artifacts": [], "run_id": 1,
                       "html_url": "https://github.com/owner/site/actions/runs/1"}
        self.artifact = b""

    def status(self):
        return {"configured": True, "message": "Injected GitHub fixture"}

    async def close(self):
        self.closed = True

    async def list_repositories(self):
        return [await self.authorize(3, 7)]

    async def authorize(self, installation_id, repository_id):
        self.counts["authorize"] += 1
        if self.revoked or (installation_id, repository_id) != (3, 7):
            raise GitHubError("Repository access was revoked.", "forbidden")
        return self.repo

    async def head(self, repo, branch):
        return self.branches[branch]

    async def branch_head(self, repo, branch):
        return self.branches.get(branch)

    async def sources(self, repo, sha, app_subdir=""):
        return copy.deepcopy(self.snapshots[sha])

    def _lost(self, stage):
        if self.lose_once == stage:
            self.lose_once = None
            raise GitHubError("GitHub write outcome is uncertain.", "uncertain")

    async def create_branch(self, repo, branch, base_sha):
        assert branch.startswith("seopilot/") and branch != "main"
        assert branch not in self.branches
        self.counts["branch"] += 1
        self.branches[branch] = base_sha
        self._lost("branch")

    async def commit(self, repo, branch, expected_head, files, message):
        assert self.branches[branch] == expected_head
        assert all(path.endswith("/page.tsx") for path in files)
        self.counts["commit"] += 1
        sha = f"{self.counts['commit'] + 100:040x}"
        self.snapshots[sha] = {**self.snapshots[expected_head], **files}
        self.parents[sha] = expected_head
        self.changed[sha] = copy.deepcopy(files)
        self.branches[branch] = sha
        self._lost("commit")
        return sha

    async def verify_commit(self, repo, sha, base_sha, files):
        return self.parents.get(sha) == base_sha and self.changed.get(sha) == files

    async def find_pull_request(self, repo, branch):
        return copy.deepcopy(self.pulls.get(branch))

    async def create_pull_request(self, repo, branch, base, title, body):
        assert branch not in self.pulls and "seopilot-manifest" in body
        self.counts["pr"] += 1
        self.pulls[branch] = {"number": self.counts["pr"], "html_url": f"https://github.com/owner/site/pull/{self.counts['pr']}",
            "head": {"sha": self.branches[branch], "ref": branch}, "base": {"ref": base},
            "state": "open", "draft": True, "merged": False, "body": body}
        self._lost("pr")
        return copy.deepcopy(self.pulls[branch])

    async def get_pull_request(self, repo, number):
        return copy.deepcopy(next(value for value in self.pulls.values() if value["number"] == number))

    async def validation(self, repo, workflow, sha):
        return copy.deepcopy(self.checks)

    async def artifact_bytes(self, repo, artifact_id):
        assert artifact_id == 5
        return self.artifact


def audit_fixture():
    page = Page(url=URL, status_code=200, title=OLD_TITLE, description=OLD_DESCRIPTION)
    issue = Issue(rule_id="title_length", title="Review title", url=URL, page_ids=[page.id], severity="Low",
        category="Metadata", explanation="Contextual title guidance", evidence=[Evidence(field="title", value=OLD_TITLE)],
        recommended_fix="Review the page title")
    rec = Recommendation(kind="title", title="Reviewed title", url=URL, page_id=page.id, suggested_value=TITLE,
        rationale="Accurate description", priority="Low", status="approved")
    return Audit(url=URL, origin=ORIGIN, status="completed", pages=[page], issues=[issue], recommendations=[rec],
                 coverage=Coverage(attempted=1, assessed=1), score=Score(value=98, assessed_pages=1))


class Workflow:
    def __init__(self, client, app, fake, audit, project):
        self.client, self.app, self.fake, self.audit, self.project = client, app, fake, audit, project
        self.store = app.state.store

    def post(self, path, payload=None):
        return self.client.post("/api/" + path, json=payload or {})

    def get(self, run_id):
        return self.client.get("/api/fix-runs/" + run_id).json()

    def tick(self):
        self.app.state.fix_engine.last_poll.clear()
        self.client.portal.call(self.app.state.fix_engine.tick)

    def create(self, **updates):
        request = {"project_id": self.project["id"], "audit_id": self.audit.id,
                   "edits": [{"url": URL, "title": TITLE, "description": DESCRIPTION}], **updates}
        response = self.post("fix-runs", request)
        assert response.status_code == 202, response.text
        run = response.json()
        self.tick()
        return self.get(run["id"])

    def publish(self, run):
        response = self.post(f"fix-runs/{run['id']}/publish",
            {"patch_hash": run["patch_hash"], "confirms_publication": True})
        assert response.status_code == 202, response.text
        self.tick()
        return self.get(run["id"])


@contextmanager
def workflow_context(path, fake=None, *, existing_audit=None, existing_project=None):
    fake = fake or FakeGitHub()
    app = create_app(path, start_worker=False, github_client=fake, settings=Settings(ai_enabled=False))
    with TestClient(app, base_url="http://localhost") as client:
        audit = existing_audit or audit_fixture()
        if not existing_audit:
            app.state.store.admit_audit(audit, "unknown")
        if existing_project:
            project = existing_project
        else:
            response = client.post("/api/projects", json={"name": "Owned pilot", "production_origin": ORIGIN,
                "installation_id": 3, "repository_id": 7, "base_branch": "main", "confirms_ownership": True})
            assert response.status_code == 201, response.text
            project = response.json()
        yield Workflow(client, app, fake, audit, project)


@pytest.fixture
def workflow(tmp_path, monkeypatch):
    for name in ("GITHUB_APP_ID", "GITHUB_APP_PRIVATE_KEY_PATH", "GITHUB_APP_OWNERS"):
        monkeypatch.delenv(name, raising=False)
    with workflow_context(tmp_path / "workflow.db") as value:
        yield value


def test_reviewed_proposal_requires_separate_exact_hash_publication(workflow, monkeypatch):
    import seopilot.ai

    async def no_ai(*args, **kwargs):
        pytest.fail("Private repository workflow must make zero AI calls")

    monkeypatch.setattr(seopilot.ai, "enrich", no_ai)
    monkeypatch.setattr(seopilot.ai, "OpenAIProvider", lambda *args, **kwargs: pytest.fail("No AI provider may receive source"))
    before = workflow.store.ai_calls_remaining(20)
    run = workflow.create()
    assert run["status"] == "proposed" and run["base_sha"] == BASE and len(run["patch_hash"]) == 64
    assert run["changed_files"] == ["app/page.tsx"] and run["changed_lines"] <= 100
    assert workflow.fake.counts["branch"] == workflow.fake.counts["commit"] == workflow.fake.counts["pr"] == 0
    assert CANARY not in json.dumps(run)
    patch = workflow.client.get(f"/api/fix-runs/{run['id']}/patch").json()
    assert patch["patch_hash"] == run["patch_hash"] and TITLE in patch["patch"]
    assert "layout.tsx" not in patch["patch"]
    rejected = workflow.post(f"fix-runs/{run['id']}/publish", {"patch_hash": "0" * 64, "confirms_publication": True})
    assert rejected.status_code == 409
    assert workflow.post(f"fix-runs/{run['id']}/publish", {"patch_hash": run["patch_hash"]}).status_code == 422
    published = workflow.publish(run)
    assert published["status"] == "pr_opened" and published["pr_url"].endswith("/1")
    assert workflow.fake.branches["main"] == BASE
    assert workflow.fake.snapshots[published["head_sha"]]["app/layout.tsx"] == workflow.fake.snapshots[BASE]["app/layout.tsx"]
    assert CANARY in workflow.fake.snapshots[published["head_sha"]]["app/page.tsx"]
    assert workflow.store.ai_calls_remaining(20) == before
    workflow.publish(published)
    assert [workflow.fake.counts[key] for key in ("branch", "commit", "pr")] == [1, 1, 1]


@pytest.mark.parametrize("stage", ["branch", "commit", "pr"])
def test_lost_write_response_is_reconciled_after_restart_without_duplicates(tmp_path, stage):
    path, fake = tmp_path / "recovery.db", FakeGitHub()
    with workflow_context(path, fake) as first:
        run = first.create()
        fake.lose_once = stage
        waiting = first.publish(run)
        assert waiting["status"] == "publishing"
        audit, project = first.audit, first.project
    with workflow_context(path, fake, existing_audit=audit, existing_project=project) as resumed:
        resumed.tick()
        assert resumed.get(run["id"])["status"] == "pr_opened"
        assert [fake.counts[key] for key in ("branch", "commit", "pr")] == [1, 1, 1]
        assert resumed.store.quota("unknown")["used"] == 1
        assert resumed.store.fixes.publication_remaining() == 1


def test_stale_base_and_conflicting_branch_never_publish(workflow):
    run = workflow.create()
    workflow.fake.branches["main"] = "c" * 40
    rejected = workflow.publish(run)
    assert rejected["status"] == "conflict"
    assert workflow.fake.counts["branch"] == workflow.fake.counts["commit"] == workflow.fake.counts["pr"] == 0
    workflow.fake.branches["main"] = BASE
    next_run = workflow.create()
    workflow.fake.branches[next_run["branch"]] = "d" * 40
    rejected = workflow.publish(next_run)
    assert rejected["status"] == "conflict" and workflow.fake.counts["commit"] == 0


def test_revoked_repository_and_forged_connection_are_denied(workflow):
    bad = workflow.post("projects", {"name": "Forged", "production_origin": "https://example.net",
        "installation_id": 3, "repository_id": 999, "base_branch": "main", "confirms_ownership": True})
    assert bad.status_code == 403
    run = workflow.create()
    workflow.fake.revoked = True
    blocked = workflow.publish(run)
    assert blocked["status"] == "publishing" and workflow.fake.counts["branch"] == 0


def test_one_active_run_cancellation_and_immediate_private_purge(workflow):
    run = workflow.create()
    duplicate = workflow.post("fix-runs", {"project_id": workflow.project["id"], "audit_id": workflow.audit.id,
                                         "edits": [{"url": URL, "title": TITLE}]})
    assert duplicate.status_code == 409
    cancelled = workflow.post(f"fix-runs/{run['id']}/cancel")
    assert cancelled.json()["status"] == "cancelled" and cancelled.json()["source_purged"]
    assert workflow.client.get(f"/api/fix-runs/{run['id']}/patch").status_code == 410
    assert not list(workflow.store.fixes.artifacts.glob("*.json"))
    assert workflow.create()["status"] == "proposed"


@pytest.mark.parametrize("action", ["cancel", "delete-source", "disconnect"])
def test_deletion_interrupts_active_source_fetch_before_acquiring_worker_lock(workflow, monkeypatch, action):
    started, cancelled = threading.Event(), threading.Event()

    async def blocked_sources(*args):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    monkeypatch.setattr(workflow.fake, "sources", blocked_sources)
    response = workflow.post("fix-runs", {"project_id": workflow.project["id"], "audit_id": workflow.audit.id,
                                          "edits": [{"url": URL, "title": TITLE}]})
    assert response.status_code == 202
    run = response.json()
    task = workflow.client.portal.start_task_soon(workflow.app.state.fix_engine.tick)
    try:
        assert started.wait(timeout=5), "The injected source stage did not start"
        route = f"projects/{workflow.project['id']}/disconnect" if action == "disconnect" else f"fix-runs/{run['id']}/{action}"
        assert workflow.post(route).status_code == 200
        task.result(timeout=5)
        assert cancelled.is_set()
        saved = workflow.get(run["id"])
        assert saved["status"] == "cancelled" and saved["source_purged"]
        assert not list(workflow.store.fixes.artifacts.glob("*.json"))
        assert workflow.fake.counts["branch"] == 0
    finally:
        task.cancel()


def test_preparing_checkpoint_recovers_when_artifact_was_written_before_crash(workflow):
    response = workflow.post("fix-runs", {"project_id": workflow.project["id"], "audit_id": workflow.audit.id,
                                          "edits": [{"url": URL, "title": TITLE}]})
    assert response.status_code == 202
    preparing = response.json()
    workflow.tick()
    assert workflow.get(preparing["id"])["status"] == "proposed"
    # Reproduce only the durable boundary of a crash: new artifact, previous SQLite checkpoint.
    with workflow.store.connection() as db:
        db.execute("UPDATE fix_runs SET status=?,payload=? WHERE id=?", ("preparing", json.dumps(preparing), preparing["id"]))
    workflow.tick()
    recovered = workflow.get(preparing["id"])
    assert recovered["status"] == "proposed" and len(recovered["targets"]) == 1
    assert workflow.fake.counts["branch"] == 0


def test_disconnect_purges_all_patches_without_deleting_remote_pr(workflow):
    run = workflow.publish(workflow.create())
    response = workflow.post(f"projects/{workflow.project['id']}/disconnect")
    assert response.status_code == 200 and not response.json()["connected"]
    saved = workflow.get(run["id"])
    assert saved["status"] == "cancelled" and saved["source_purged"]
    assert workflow.fake.closed and len(workflow.fake.pulls) == 1
    assert workflow.post("fix-runs", {"project_id": workflow.project["id"], "audit_id": workflow.audit.id,
                                      "edits": [{"url": URL, "title": TITLE}]}).status_code == 409


def test_two_publications_per_day_remain_spent_after_cancellation(workflow):
    for _ in range(2):
        published = workflow.publish(workflow.create())
        assert published["status"] == "pr_opened"
        assert workflow.post(f"fix-runs/{published['id']}/cancel").status_code == 200
    third = workflow.create()
    denied = workflow.post(f"fix-runs/{third['id']}/publish",
                           {"patch_hash": third["patch_hash"], "confirms_publication": True})
    assert denied.status_code == 429 and denied.headers["Retry-After"]
    assert workflow.fake.counts["pr"] == 2 and workflow.store.fixes.publication_remaining() == 0


@pytest.mark.parametrize("edit", [{"url": "https://attacker.test/", "title": TITLE},
    {"url": URL + "?page=1", "title": TITLE}, {"url": URL, "title": "\nunsafe"}, {"url": URL},
    {"url": URL, "title": "Not the approved suggestion", "recommendation_ids": ["forged"]}])
def test_invalid_metadata_and_unapproved_text_references_are_rejected(workflow, edit):
    response = workflow.post("fix-runs", {"project_id": workflow.project["id"], "audit_id": workflow.audit.id,
                                         "edits": [edit]})
    assert response.status_code in {409, 422}
    assert not workflow.store.fixes.history() and workflow.fake.counts["branch"] == 0


def test_approved_recommendation_content_never_authorizes_publication(workflow):
    rec = workflow.audit.recommendations[0]
    run = workflow.create(edits=[{"url": URL, "title": TITLE, "recommendation_ids": [rec.id]}])
    assert run["status"] == "proposed" and workflow.fake.counts["pr"] == 0, run["message"]
    assert workflow.store.get(workflow.audit.id).recommendations[0].status == "approved"


def validation_archive(run, *, head_sha=None, title=None):
    screenshot = "screenshots/page-1.png"
    target = run["targets"][0]
    checks = ["http", "title", "description", "content", "console", "page_errors", "canonical", "robots"]
    report = {"schema_version": 1, "fix_run_id": run["id"], "patch_hash": run["patch_hash"],
        "head_sha": head_sha or run["head_sha"], "run_id": 1, "status": "passed",
        "checks": [{"name": name, "status": "passed" if name in {"install", "build", "render"} else "skipped"}
                   for name in ["install", "build", "render", "lint", "typecheck", "test"]],
        "targets": [{"url": target["url"], "route": target["route"], "title": title or target["title"],
            "description": target["description"], "canonical": target["canonical"], "robots": target["robots"],
            "status_code": 200, "content_characters": 80, "console_errors": 0, "page_errors": 0,
            "checks": [{"name": name, "status": "passed"} for name in checks], "screenshot": screenshot}]}
    result = io.BytesIO()
    with zipfile.ZipFile(result, "w") as archive:
        archive.writestr("validation.json", json.dumps(report))
        archive.writestr(screenshot, b"\x89PNG\r\n\x1a\nfixture")
    return result.getvalue()


@pytest.mark.parametrize("mode", ["failure", "missing", "wrong_sha", "wrong_render", "passed"])
def test_hosted_validation_must_match_exact_commit_and_rendered_metadata(workflow, mode):
    run = workflow.publish(workflow.create())
    workflow.fake.checks.update(status="completed", conclusion="failure" if mode == "failure" else "success")
    if mode not in {"failure", "missing"}:
        workflow.fake.checks["artifacts"] = [{"id": 5, "name": "seopilot-validation-" + run["head_sha"],
                                             "expired": False, "size_in_bytes": 1000}]
        workflow.fake.artifact = validation_archive(run, head_sha="c" * 40 if mode == "wrong_sha" else None,
                                                     title="Unexpected metadata" if mode == "wrong_render" else None)
    workflow.tick()
    checked = workflow.get(run["id"])
    assert checked["status"] == ("checks_passed" if mode == "passed" else "checks_failed")
    assert checked["validation"]["status"] == ("passed" if mode == "passed" else "missing" if mode == "missing" else "failed")
    assert workflow.fake.counts["commit"] == 1 and workflow.store.ai_calls_remaining(20) == 20


def test_dispositions_preserve_original_evidence_and_historical_score(workflow):
    original = workflow.store.get(workflow.audit.id)
    issue = original.issues[0]
    response = workflow.client.patch(f"/api/audits/{original.id}/issues/{issue.id}/disposition",
                                    json={"status": "intentional", "reason": "Brand wording is intentional"})
    assert response.status_code == 200 and response.json()["recorded_at"]
    after = workflow.store.get(original.id)
    assert after.issues == original.issues and after.score == original.score
    assert len(workflow.client.get(f"/api/audits/{original.id}/dispositions").json()) == 1


def merge(workflow, run):
    workflow.fake.pulls[run["branch"]]["merged"] = True
    workflow.fake.pulls[run["branch"]]["state"] = "closed"
    workflow.tick()
    assert workflow.get(run["id"])["status"] == "awaiting_deployment"


@pytest.mark.parametrize("deployed", [False, True])
def test_merge_is_separate_from_bounded_live_verification_with_ai_disabled(workflow, deployed):
    run = workflow.publish(workflow.create())
    assert workflow.post(f"fix-runs/{run['id']}/verify").status_code == 409
    merge(workflow, run)
    response = workflow.post(f"fix-runs/{run['id']}/verify")
    assert response.status_code == 202
    verification_id = response.json()["verification_audit_id"]
    audit = workflow.store.get(verification_id)
    assert audit.allow_ai is False and audit.verification_urls == [URL]
    assert audit.options.page_limit == 1 and audit.options.max_depth == 0
    assert workflow.post(f"fix-runs/{run['id']}/verify").json()["verification_audit_id"] == verification_id
    audit.status = "completed"
    audit.pages = [Page(url=URL, status_code=200, title=TITLE if deployed else OLD_TITLE,
                        description=DESCRIPTION if deployed else OLD_DESCRIPTION)]
    audit.coverage = Coverage(attempted=1, assessed=1)
    workflow.store.save(audit)
    workflow.tick()
    saved = workflow.get(run["id"])
    assert saved["status"] == ("live_verified" if deployed else "verification_failed")
    assert workflow.store.get(workflow.audit.id).score.value == 98
    assert workflow.store.quota("unknown")["used"] == 2
    assert workflow.store.ai_calls_remaining(20) == 20


def test_live_verification_cannot_bypass_existing_daily_audit_allowance(workflow):
    run = workflow.publish(workflow.create())
    merge(workflow, run)
    for path in ("/other-one", "/other-two"):
        workflow.store.admit_audit(Audit(url=ORIGIN + path, origin=ORIGIN, status="completed"), "unknown")
    assert workflow.store.quota("unknown")["used"] == 3
    assert workflow.post(f"fix-runs/{run['id']}/verify").status_code == 429
    assert workflow.get(run["id"])["verification_audit_id"] is None


def test_failed_live_verification_can_recheck_new_deployment_without_reusing_old_evidence(workflow):
    run = workflow.publish(workflow.create())
    merge(workflow, run)
    first = workflow.post(f"fix-runs/{run['id']}/verify").json()
    failed = workflow.store.get(first["verification_audit_id"])
    failed.status = "completed"
    failed.pages = [Page(url=URL, status_code=200, title=OLD_TITLE, description=OLD_DESCRIPTION)]
    workflow.store.save(failed)
    workflow.tick()
    assert workflow.get(run["id"])["status"] == "verification_failed"
    second = workflow.post(f"fix-runs/{run['id']}/verify")
    assert second.status_code == 202
    assert second.json()["verification_audit_id"] != failed.id
    assert workflow.store.quota("unknown")["used"] == 3


def test_stable_finding_keys_ignore_generated_ids_and_reduced_coverage_is_not_clean():
    before = audit_fixture()
    target = FixTarget(url=URL, route="/", path="app/page.tsx", title=TITLE, description=DESCRIPTION)
    run = FixRun(project_id=str(uuid4()), audit_id=before.id, repository_id=7, base_branch="main", base_sha=BASE,
        patch_hash="f"*64, expires_at="2099-01-01T00:00:00+00:00", targets=[target], changed_files=[target.path], changed_lines=2)
    after = before.model_copy(deep=True)
    after.id, after.issues[0].id, after.issues[0].evidence[0].id = str(uuid4()), str(uuid4()), str(uuid4())
    after.pages[0].title, after.pages[0].description = TITLE, DESCRIPTION
    same = compare_live(before, after, run)
    assert same["status"] == "verified" and same["resolved"] == same["new"] == []
    after.pages = []
    after.coverage = Coverage(attempted=1, blocked=1, unchecked=1)
    reduced = compare_live(before, after, run)
    assert reduced["status"] == "failed" and reduced["checks"][0]["outcome"] == "unchecked"
    assert reduced["resolved"] == [] and not reduced["score_comparable"]
    after = before.model_copy(deep=True)
    after.pages[0].title, after.pages[0].description = TITLE, DESCRIPTION
    after.pages[0].truncated_fields = ["canonicals"]
    assert compare_live(before, after, run)["status"] == "failed"


def test_persisted_poll_window_pauses_and_explicit_refresh_resumes(workflow):
    run = workflow.create()
    response = workflow.post(f"fix-runs/{run['id']}/publish", {"patch_hash": run["patch_hash"], "confirms_publication": True})
    assert response.status_code == 202
    saved = workflow.store.fixes.get(run["id"])
    saved.poll_until = "2000-01-01T00:00:00+00:00"
    workflow.store.fixes.save(saved)
    workflow.tick()
    assert workflow.fake.counts["pr"] == 0
    assert workflow.post(f"fix-runs/{run['id']}/refresh").status_code == 202
    workflow.tick()
    assert workflow.get(run["id"])["status"] == "pr_opened"


def test_patch_export_applies_when_source_has_no_final_newline(tmp_path):
    import subprocess

    from seopilot.fix_engine import unified_patch

    folder = tmp_path / "app"
    folder.mkdir()
    (folder / "page.tsx").write_text("export const metadata = { title: 'Old' };", encoding="utf-8")
    patch = unified_patch("export const metadata = { title: 'Old' };", "export const metadata = { title: 'New' };", "app/page.tsx")
    result = subprocess.run(["git", "apply", "--check", "-"], cwd=tmp_path, input=patch.encode(), capture_output=True)
    assert result.returncode == 0, result.stderr.decode()
