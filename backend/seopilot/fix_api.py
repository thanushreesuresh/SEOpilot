"""Explicit operator actions for locally connected, owned repositories."""

import asyncio
import re
from datetime import datetime, timedelta, timezone
from pathlib import PurePosixPath
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request

from .fix_models import (
    ConnectionStatus,
    DispositionRequest,
    FindingDisposition,
    FixRequest,
    FixRun,
    PatchExport,
    Project,
    ProjectRequest,
    PublishRequest,
    poll_deadline,
)
from .models import Audit, CrawlOptions, now
from .network import normalize_url, origin_of


def _subdirectory(value: str) -> str:
    if not value:
        return ""
    if not re.fullmatch(r"[A-Za-z0-9_./-]+", value) or any(part in {"..", ".", ""} for part in value.split("/")):
        raise ValueError("Use a repository-relative application directory without dot segments.")
    if PurePosixPath(value).is_absolute() or value.startswith("."):
        raise ValueError("Invalid application directory.")
    return value


def router() -> APIRouter:
    api = APIRouter(prefix="/api")

    @api.get("/github/connection", response_model=ConnectionStatus)
    async def connection(request: Request):
        from .github_app import GitHubError

        client = request.app.state.github
        status = client.status()
        values = {"configured": status["configured"], "state": "setup_required",
                  "setup_checks": status.get("setup_checks", []), "checked_at": now(),
                  "message": "Add the missing GitHub App settings to backend/.env and restart the backend. Never enter credentials in this dashboard."}
        if status.get("invalid_settings"):
            values["state"] = "invalid_settings"
            values["message"] = "One or more GitHub App settings are invalid. Use a positive numeric App ID, comma-separated GitHub owner names and an absolute PEM file path in backend/.env, then restart the backend. Website auditing remains available."
        elif status["configured"]:
            try:
                repositories = await client.list_repositories()
                values["repositories"] = [{key: getattr(repo, key) for key in ("id", "installation_id", "owner", "name", "default_branch")} for repo in repositories]
                values["state"] = "ready" if repositories else "no_repositories"
                values["message"] = ("GitHub verified the selected repositories. Confirm your website mapping before preparing a patch."
                                     if repositories else "No eligible repositories were returned. Install the App on selected repositories in an allowed owner account, then refresh.")
            except GitHubError as exc:
                # Provider messages can contain private details; only fixed guidance crosses this boundary.
                values["state"] = {"credentials": "credentials_error", "not_configured": "credentials_error",
                                   "forbidden": "access_denied", "not_found": "access_denied",
                                   "limited": "rate_limited"}.get(exc.code, "unavailable")
            except Exception:
                values["state"] = "unavailable"
            guidance = {
                "credentials_error": "GitHub authentication could not be completed. Check the numeric App ID, matching readable PEM file and computer clock, then restart the backend and refresh.",
                "access_denied": "GitHub denied access or an API limit was reached. Check installation access, selected repositories, owner allowlist and required permissions before retrying.",
                "rate_limited": "GitHub's API request limit was reached. Wait before refreshing; repeated clicks will not restore access.",
                "unavailable": "GitHub verification is unavailable. Check your network and local App setup, then refresh. No repository access is confirmed by this result.",
            }
            if values["state"] in guidance:
                values["message"] = guidance[values["state"]]
        return ConnectionStatus(**values, publications_remaining=request.app.state.store.fixes.publication_remaining())

    @api.get("/projects", response_model=list[Project])
    async def projects(request: Request):
        return request.app.state.store.fixes.projects()

    @api.post("/projects", response_model=Project, status_code=201)
    async def connect(body: ProjectRequest, request: Request):
        from .github_app import GitHubError

        try:
            url = normalize_url(body.production_origin)
            if url.rstrip("/") != origin_of(url):
                raise ValueError("Enter the production origin, without a path or query.")
            subdirectory = _subdirectory(body.app_subdirectory)
            if not re.fullmatch(r"[A-Za-z0-9_./-]+", body.base_branch) or ".." in body.base_branch or body.base_branch.startswith(("-", "/")):
                raise ValueError("Invalid base branch.")
            repo = await request.app.state.github.authorize(body.installation_id, body.repository_id)
            await request.app.state.github.head(repo, body.base_branch)
            project = Project(name=body.name, production_origin=origin_of(url), installation_id=repo.installation_id,
                              repository_id=repo.id, repository_owner=repo.owner, repository_name=repo.name,
                              base_branch=body.base_branch, app_subdirectory=subdirectory, workflow=body.workflow)
            return request.app.state.store.fixes.connect(project)
        except GitHubError:
            raise HTTPException(403, "Repository access could not be verified. Check the selected GitHub App installation.") from None
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from None

    @api.post("/projects/{project_id}/disconnect", response_model=Project)
    async def disconnect(project_id: UUID, request: Request):
        fixes = request.app.state.store.fixes
        await request.app.state.fix_engine.interrupt(project_id=str(project_id))
        async with request.app.state.fix_lock:
            project = fixes.project(str(project_id))
            if project is None:
                raise HTTPException(404, "Project not found")
            project.connected = False
            fixes.save_project(project)
            for run in fixes.all_runs(project.id):
                if run.project_id == project.id:
                    if run.status not in {"live_verified", "cancelled", "expired"}:
                        run.status = "cancelled"
                        run.message = "Project disconnected. Existing GitHub branches and PRs remain available for manual review."
                    fixes.purge(run)
            # Installation tokens only live in memory; disconnect drops that cache too.
            await request.app.state.github.close()
            from .github_app import GitHubClient
            request.app.state.github = GitHubClient.from_env()
            request.app.state.fix_engine.github = request.app.state.github
            return project

    @api.get("/audits/{audit_id}/dispositions", response_model=list[FindingDisposition])
    async def dispositions(audit_id: UUID, request: Request):
        return request.app.state.store.fixes.dispositions(str(audit_id))

    @api.patch("/audits/{audit_id}/issues/{issue_id}/disposition", response_model=FindingDisposition)
    async def disposition(audit_id: UUID, issue_id: UUID, body: DispositionRequest, request: Request):
        store = request.app.state.store
        audit = store.get(str(audit_id))
        issue = next((issue for issue in audit.issues if issue.id == str(issue_id)), None) if audit else None
        if issue is None:
            raise HTTPException(404, "Finding not found")
        value = FindingDisposition(audit_id=audit.id, issue_id=issue.id, rule_id=issue.rule_id, url=issue.url,
                                   status=body.status, reason=body.reason)
        store.fixes.disposition(value)
        return value

    @api.get("/fix-runs", response_model=list[FixRun])
    async def fixes(request: Request):
        return request.app.state.store.fixes.history()

    def get_run(request: Request, run_id: UUID):
        run = request.app.state.store.fixes.get(str(run_id))
        if run is None:
            raise HTTPException(404, "Fix run not found")
        return run

    @api.get("/fix-runs/{run_id}", response_model=FixRun)
    async def fix(run_id: UUID, request: Request):
        return get_run(request, run_id)

    @api.post("/fix-runs/{run_id}/refresh", response_model=FixRun, status_code=202)
    async def refresh_fix(run_id: UUID, request: Request):
        async with request.app.state.fix_lock:
            run = get_run(request, run_id)
            run.poll_until = poll_deadline()
            request.app.state.store.fixes.save(run)
            request.app.state.fix_engine.last_poll.pop(run.id, None)
            return run

    @api.post("/fix-runs", response_model=FixRun, status_code=202)
    async def create_fix(body: FixRequest, request: Request):
        from urllib.parse import unquote, urlsplit

        store = request.app.state.store
        async with request.app.state.fix_lock:
            project = store.fixes.project(body.project_id)
            audit = store.get(body.audit_id)
            if project is None or not project.connected:
                raise HTTPException(409, "Connect the project before creating a proposal.")
            if audit is None or audit.mode != "live" or audit.origin != project.production_origin or audit.status not in {"completed", "partial"}:
                raise HTTPException(409, "Choose a finished live audit of this project's production origin.")
            edits = []
            for item in body.edits:
                try:
                    url = normalize_url(item.url)
                except ValueError:
                    raise HTTPException(422, "Invalid affected URL") from None
                if origin_of(url) != project.production_origin or urlsplit(url).query or urlsplit(url).fragment or "%" in urlsplit(url).path or any(part in {".", ".."} for part in unquote(urlsplit(url).path).split("/")):
                    raise HTTPException(422, "Use an unambiguous static page URL on the project's production origin.")
                if not any(page.url == url and page.outcome == "html" and not any(field in page.truncated_fields for field in ("title", "description", "canonicals", "robots")) for page in audit.pages):
                    raise HTTPException(409, "The affected page needs complete HTML metadata evidence in the selected audit.")
                if item.title is None and item.description is None:
                    raise HTTPException(422, "Enter a title or description.")
                for value in (item.title, item.description):
                    if value is not None and (not value.strip() or any(ord(char) < 32 for char in value)):
                        raise HTTPException(422, "Metadata must be nonempty text without control characters.")
                for rec_id in item.recommendation_ids:
                    rec = next((rec for rec in audit.recommendations if rec.id == rec_id), None)
                    if rec is None or rec.status != "approved" or rec.url != url or rec.kind not in {"title", "description"} or getattr(item, rec.kind) != rec.suggested_value:
                        raise HTTPException(409, "Only approved title/description text from this page can be reused.")
                edits.append({**item.model_dump(exclude={"recommendation_ids"}, exclude_none=True), "url": url})
            if len({edit["url"] for edit in edits}) != len(edits):
                raise HTTPException(422, "Select each page once.")
            run = FixRun(project_id=project.id, audit_id=audit.id, repository_id=project.repository_id,
                base_branch=project.base_branch, base_sha="", patch_hash="", targets=[], changed_files=[], changed_lines=0,
                expires_at=(datetime.now(timezone.utc)+timedelta(hours=24)).isoformat(), status="preparing",
                message="Queued for static source inspection. No AI calls or GitHub writes will be made.")
            run.branch = "seopilot/"+run.id
            try:
                store.fixes.cleanup()
                store.fixes.create(run)
                store.fixes.write_artifact(run.id, {"edits": edits})
            except ValueError as exc:
                raise HTTPException(409, str(exc)) from None
            return run

    @api.get("/fix-runs/{run_id}/patch", response_model=PatchExport)
    async def export_patch(run_id: UUID, request: Request):
        run = get_run(request, run_id)
        try:
            data = request.app.state.store.fixes.artifact(run)
            if "patch" not in data:
                raise ValueError("Wait for the proposal to finish preparing.")
            return PatchExport(filename=f"seopilot-{run.id}.patch", patch=data["patch"], patch_hash=run.patch_hash)
        except ValueError as exc:
            raise HTTPException(410, str(exc)) from None

    @api.post("/fix-runs/{run_id}/publish", response_model=FixRun, status_code=202)
    async def publish(run_id: UUID, body: PublishRequest, request: Request):
        async with request.app.state.fix_lock:
            run = get_run(request, run_id)
            if body.patch_hash != run.patch_hash:
                raise HTTPException(409, "The approved hash does not match this exact proposal.")
            if run.status in {"publishing", "pr_opened", "checks_passed", "checks_failed", "awaiting_deployment", "live_verified"}:
                return run
            if run.status != "proposed":
                raise HTTPException(409, "Only a reviewed, current proposal can be published.")
            try:
                request.app.state.store.fixes.artifact(run)
            except ValueError as exc:
                raise HTTPException(410, str(exc)) from None
            if not request.app.state.store.fixes.reserve_publication(run.id):
                raise HTTPException(429, "The limit of two draft PR publications per rolling 24 hours has been reached.", headers={"Retry-After": "86400"})
            run.status, run.message = "publishing", "Publication approved for this exact patch. Reconciling the dedicated branch before any write."
            run.poll_until = poll_deadline()
            request.app.state.store.fixes.save(run)
            request.app.state.fix_engine.last_poll.pop(run.id, None)
            return run

    @api.post("/fix-runs/{run_id}/cancel", response_model=FixRun)
    async def cancel(run_id: UUID, request: Request):
        await request.app.state.fix_engine.interrupt(run_id=str(run_id))
        async with request.app.state.fix_lock:
            run = get_run(request, run_id)
            run.status = "cancelled"
            run.message = "Cancelled locally and private patch deleted. Any existing GitHub PR remains available for manual review."
            request.app.state.store.fixes.purge(run)
            return run

    @api.post("/fix-runs/{run_id}/delete-source", response_model=FixRun)
    async def delete_source(run_id: UUID, request: Request):
        await request.app.state.fix_engine.interrupt(run_id=str(run_id))
        async with request.app.state.fix_lock:
            run = get_run(request, run_id)
            if run.status in {"preparing", "proposed", "publishing"}:
                run.status = "cancelled"
            request.app.state.store.fixes.purge(run)
            return run

    @api.post("/fix-runs/{run_id}/verify", response_model=FixRun, status_code=202)
    async def verify(run_id: UUID, request: Request):
        async with request.app.state.fix_lock:
            store = request.app.state.store
            run = get_run(request, run_id)
            if run.status not in {"awaiting_deployment", "verification_failed"}:
                raise HTTPException(409, "Wait for the PR to merge, then deploy before starting live verification.")
            project = store.fixes.project(run.project_id)
            if not project or not project.connected:
                raise HTTPException(409, "The project is disconnected.")
            if run.verification_audit_id:
                previous = store.get(run.verification_audit_id)
                if previous and previous.status in {"queued", "crawling", "analyzing", "reviewing"}:
                    return run
            urls = [target.url for target in run.targets]
            audit = Audit(url=urls[0], origin=project.production_origin, allow_ai=False,
                verification_urls=urls, options=CrawlOptions(page_limit=len(urls), max_depth=0))
            admitted, reason, quota = store.admit_audit(audit, request.state.identity)
            if admitted is None:
                raise HTTPException(429, "Live verification uses the existing daily audit allowance. Wait for capacity or its reset.",
                    headers={"Retry-After": str(quota["retry_after"] or 30)})
            run.verification_audit_id = admitted.id
            run.poll_until = poll_deadline()
            run.status, run.message = "awaiting_deployment", "Live verification queued with AI disabled; merge status alone is not verification."
            store.fixes.save(run)
            request.app.state.fix_engine.last_poll.pop(run.id, None)
            return run

    return api


def initialize(app, github_client=None):
    from .github_app import GitHubClient

    app.state.github = github_client or GitHubClient.from_env()
    app.state.fix_lock = asyncio.Lock()
