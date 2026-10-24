"""Deterministic proposal/publish/reconcile workflow. This module never imports AI services."""

import asyncio
import difflib
import hashlib
import json
import time
from contextlib import suppress
from datetime import datetime
from urllib.parse import urlsplit

from .audit_reporting import compare_audits
from .fix_models import FixRun, FixTarget, ValidationResult
from .fix_storage import TERMINAL
from .models import Audit
from .network import normalize_url


def patch_digest(binding: dict, patch: str) -> str:
    return hashlib.sha256((json.dumps(binding, sort_keys=True, ensure_ascii=True)+"\n"+patch).encode()).hexdigest()


def unified_patch(before: str, after: str, path: str) -> str:
    lines = difflib.unified_diff(before.splitlines(keepends=True), after.splitlines(keepends=True),
                                 fromfile="a/"+path, tofile="b/"+path)
    return "".join(line if line.endswith("\n") else line+"\n\\ No newline at end of file\n" for line in lines)


def compare_live(before: Audit, after: Audit, run: FixRun) -> dict:
    """Unknown/missing coverage never counts as a resolved observation."""
    try:
        comparison = compare_audits(before, after)
    except ValueError:
        comparison = None
    analysis_finished = comparison is not None and after.status in {"completed", "partial"}
    pages = {normalize_url(page.url): page for page in after.pages}
    checks = []
    for target in run.targets:
        page = pages.get(normalize_url(target.url))
        assessed = (analysis_finished and page is not None and page.outcome == "html" and page.status_code is not None
                    and 200 <= page.status_code < 300
                    and not set(page.truncated_fields) & {"body", "title", "description", "canonicals", "robots"})
        passed = bool(assessed and (target.title is None or page.title == target.title)
                      and (target.description is None or page.description == target.description)
                      and page.canonicals == target.canonical and page.robots == target.robots)
        checks.append({"url": target.url, "passed": passed, "outcome": page.outcome if page else "unchecked",
                       "metadata_matches": passed,
                       "reason": "Recorded metadata matches." if passed else
                       "The audit did not finish comparable deterministic analysis." if not analysis_finished else
                       "Complete successful metadata evidence is missing or differs from the approved values."})
    comparable = before.rules_version == after.rules_version and before.score.version == after.score.version

    def changed_keys(status):
        return [[item["rule_id"], item["url"], item["field"]] for item in comparison[status]] if comparison else []

    return {"status": "verified" if checks and all(item["passed"] for item in checks) else "failed", "checks": checks,
            "resolved": changed_keys("resolved"), "new": changed_keys("added"),
            "unresolved_unknown": comparison["unresolved_unknown"] if comparison else [],
            "comparison_limitations": comparison["limitations"] if comparison else
            ["The saved audit snapshots are incompatible; findings and scores cannot be compared."],
            "versions_match": comparable, "before_score": before.score.value, "after_score": after.score.value,
            "score_comparable": comparison is not None and comparison["score_delta"] is not None,
            "coverage": after.coverage.model_dump(),
            "note": "Historical scores are preserved. Reduced or unknown coverage is not an improvement; traffic and rankings require measurement over time."}


class FixEngine:
    def __init__(self, store, github, lock):
        self.store, self.fixes, self.github, self.lock = store, store.fixes, github, lock
        self.last_poll: dict[str, float] = {}
        self.active_task: asyncio.Task | None = None
        self.active_run: FixRun | None = None
        self.interrupted = False

    async def interrupt(self, *, run_id: str | None = None, project_id: str | None = None):
        run = self.active_run
        if run and self.active_task and (run.id == run_id or run.project_id == project_id):
            self.interrupted = True
            self.active_task.cancel()
            with suppress(asyncio.CancelledError):
                await self.active_task

    async def _stage(self, run, project):
        async with asyncio.timeout(90):
            repo = await self.github.authorize(project.installation_id, project.repository_id)
            if run.status == "preparing":
                await self.prepare(run, project, repo)
            elif run.status == "publishing":
                await self.publish(run, project, repo)
            elif run.pr_number:
                await self.refresh(run, project, repo)

    async def tick(self):
        self.fixes.cleanup()
        for run in self.fixes.all_runs():
            if run.status in TERMINAL or run.status == "proposed":
                continue
            if datetime.fromisoformat(run.poll_until).timestamp() <= time.time():
                continue
            if time.monotonic() - self.last_poll.get(run.id, -1000) < 60:
                continue
            self.last_poll[run.id] = time.monotonic()
            async with self.lock:
                run = self.fixes.get(run.id)
                if run.status in TERMINAL:
                    continue
                try:
                    project = self.fixes.project(run.project_id)
                    if project is None or not project.connected:
                        continue
                    self.active_run, self.interrupted = run, False
                    self.active_task = asyncio.create_task(self._stage(run, project))
                    await self.active_task
                except asyncio.CancelledError:
                    if not self.interrupted:
                        raise
                except Exception as error:
                    from .github_app import GitHubError
                    from .metadata_adapter import MetadataAdapterError

                    if isinstance(error, GitHubError):
                        run.message = "GitHub could not confirm this operation. Check the connection; existing writes will be reconciled before another attempt."
                        if run.status == "preparing":
                            run.status = "failed"
                    elif isinstance(error, (ValueError, MetadataAdapterError)):
                        run.status = "conflict" if run.status == "publishing" else "failed"
                        run.message = str(error)[:500] if isinstance(error, ValueError) else "This route requires a manual metadata edit."
                    else:
                        run.message = "The operation stopped safely. Review the connection and generate a new proposal if needed."
                        if run.status == "preparing":
                            run.status = "failed"
                    self.fixes.save(run)
                finally:
                    self.active_run, self.active_task = None, None
            # Do one network stage per worker iteration so queued audits get priority.
            return

    async def prepare(self, run, project, repo):
        from .metadata_adapter import generate_metadata_patch

        data = self.fixes.artifact(run)
        audit = self.store.get(run.audit_id)
        head = await self.github.head(repo, project.base_branch)
        files = await self.github.sources(repo, head, project.app_subdirectory)
        prefix = project.app_subdirectory + "/" if project.app_subdirectory else ""
        app_files = {path[len(prefix):]: text for path, text in files.items() if path.startswith(prefix)}
        if any(path.endswith(("/page.js", "/page.jsx", "/layout.js", "/layout.jsx")) for path in app_files):
            raise ValueError("JavaScript App Router metadata requires a manual edit in this release.")
        package = json.loads(app_files.get("package.json", "{}"))
        if "next" not in {**package.get("dependencies", {}), **package.get("devDependencies", {})}:
            raise ValueError("The selected directory does not declare Next.js.")
        edits = data["edits"]
        run.targets = []
        for edit in edits:
            edit["route"] = urlsplit(edit["url"]).path or "/"
        inventory = {path: text for path, text in app_files.items() if path.endswith(("/page.tsx", "/page.ts", "/layout.tsx", "/layout.ts"))}
        output = await generate_metadata_patch(inventory, edits)
        changes = output["changes"]
        if not changes:
            raise ValueError("The requested metadata already matches the repository.")
        patch = ""
        replacements = {}
        for change in changes:
            path = prefix + change["path"]
            if not path.endswith(("/page.tsx", "/page.ts")) or any(part in {"..", ".github", "node_modules"} for part in path.split("/")):
                raise ValueError("The proposal includes an unsupported file.")
            replacements[path] = change["after"]
            patch += unified_patch(change["before"], change["after"], path)
            page = next(page for page in audit.pages if normalize_url(page.url) == change["url"])
            run.targets.append(FixTarget(url=change["url"], route=change["route"], path=path,
                old_title=change.get("old_title"), old_description=change.get("old_description"),
                title=change.get("title") if change.get("title") is not None else change.get("old_title") or "",
                description=change.get("description") if change.get("description") is not None else change.get("old_description") or "",
                canonical=page.canonicals, robots=page.robots))
        changed_lines = sum(line.startswith(("+", "-")) and not line.startswith(("+++", "---")) for line in patch.splitlines())
        if len(replacements) > 5 or changed_lines > 100 or len(patch.encode()) > 256*1024:
            raise ValueError("The patch exceeds the five-file, 100-line, or 256 KiB export limit.")
        run.base_sha, run.changed_files, run.changed_lines = head, list(replacements), changed_lines
        binding = {"audit_id": run.audit_id, "project_id": run.project_id, "repository_id": run.repository_id,
                   "base_branch": run.base_branch, "base_sha": head, "targets": [target.model_dump() for target in run.targets]}
        run.patch_hash = patch_digest(binding, patch)
        self.fixes.write_artifact(run.id, {"edits": edits, "patch": patch, "files": replacements, "binding": binding})
        run.status = "proposed"
        run.message = "Review the exact diff. Content approval alone never publishes a branch. Patch generation used zero AI calls."
        self.fixes.save(run)

    def manifest(self, run, project):
        return {"schema_version": 1, "fix_run_id": run.id, "patch_hash": run.patch_hash,
                "app_subdirectory": project.app_subdirectory,
                "targets": [{key: value for key, value in target.model_dump().items()
                             if key in {"url", "route", "title", "description", "canonical", "robots"}} for target in run.targets]}

    async def publish(self, run, project, repo):
        data = None
        existing_pr = await self.github.find_pull_request(repo, run.branch)
        current = await self.github.branch_head(repo, run.branch)
        if current and current != run.base_sha:
            # Reconcile a commit whose response was lost. Exact file bytes and the one-parent chain are checked by client.
            if run.head_sha and current != run.head_sha:
                raise ValueError("The SEOPilot branch changed. Inspect the existing PR manually.")
            data = self.fixes.artifact(run)
            if not await self.github.verify_commit(repo, current, run.base_sha, data["files"]):
                raise ValueError("The existing branch contains changes outside the approved one-commit patch.")
            contents = await self.github.sources(repo, current, project.app_subdirectory)
            if any(contents.get(path) != content for path, content in data["files"].items()):
                raise ValueError("The existing branch differs from the approved patch.")
            run.head_sha = current
            self.fixes.save(run)
        elif not existing_pr:
            if await self.github.head(repo, run.base_branch) != run.base_sha:
                raise ValueError("The base branch changed. Generate and review a fresh proposal.")
            data = self.fixes.artifact(run)
            if patch_digest(data["binding"], data["patch"]) != run.patch_hash:
                raise ValueError("The stored patch no longer matches the approved hash.")
            if not current:
                await self.github.create_branch(repo, run.branch, run.base_sha)
            run.head_sha = await self.github.commit(repo, run.branch, run.base_sha, data["files"], "SEO: apply reviewed page metadata")
            self.fixes.save(run)
        if existing_pr:
            if (existing_pr.get("head", {}).get("sha") != run.head_sha
                    or existing_pr.get("head", {}).get("ref") != run.branch
                    or existing_pr.get("base", {}).get("ref") != run.base_branch):
                raise ValueError("The existing pull request head does not match the approved patch.")
            pr = existing_pr
        else:
            manifest = json.dumps(self.manifest(run, project), ensure_ascii=True, indent=2)
            pr = await self.github.create_pull_request(repo, run.branch, run.base_branch, "SEO: reviewed page titles and descriptions",
                "Reviewed metadata proposal. Manual review, merge and deployment are required.\n\n"
                f"Patch hash: `{run.patch_hash}`\n\n<!-- seopilot-manifest\n{manifest}\n-->\n")
        run.pr_number, run.pr_url = pr["number"], pr["html_url"]
        run.status = "pr_opened"
        run.message = "Draft PR opened. Review GitHub validation before manually merging and deploying."
        self.fixes.save(run)

    async def refresh(self, run, project, repo):
        from .ci_validation import validate_artifact

        pr = await self.github.get_pull_request(repo, run.pr_number)
        if (pr.get("head", {}).get("sha") != run.head_sha or pr.get("head", {}).get("ref") != run.branch
                or pr.get("base", {}).get("ref") != run.base_branch):
            run.status, run.message = "conflict", "The PR head changed; previous validation no longer applies."
            self.fixes.save(run)
            return
        if run.verification_audit_id:
            after = self.store.get(run.verification_audit_id)
            if after and after.status in {"completed", "partial", "failed", "interrupted", "cancelled"}:
                run.verification = compare_live(self.store.get(run.audit_id), after, run)
                run.status = "live_verified" if run.verification["status"] == "verified" else "verification_failed"
                run.message = "The recorded live pages match the approved metadata and indexing directives." if run.status == "live_verified" else "Live verification did not pass. Review failed, blocked or unchecked pages before retrying."
                self.fixes.save(run)
                return
        if pr.get("merged"):
            if run.status not in {"merged", "awaiting_deployment", "verification_failed"}:
                run.status = "merged"
                self.fixes.save(run)
            run.status = "awaiting_deployment"
            run.message = "PR merged. Deploy your website, then choose Verify live. A merge does not prove deployment."
        elif pr.get("state") == "closed":
            run.status, run.message = "cancelled", "The pull request was closed without merging."
        validation = await self.github.validation(repo, project.workflow, run.head_sha)
        run.validation = ValidationResult(status=validation.get("status", "pending"), summary=validation.get("summary", "Waiting for the configured validation workflow."), run_url=validation.get("html_url"))
        if validation.get("status") == "completed":
            if validation.get("conclusion") != "success":
                run.validation.status, run.validation.summary = "failed", "The configured GitHub validation workflow failed. No automatic repair or rerun was started."
            else:
                artifacts = [item for item in validation.get("artifacts", []) if item.get("name") == "seopilot-validation-"+run.head_sha and not item.get("expired")]
                if len(artifacts) != 1:
                    run.validation.status, run.validation.summary = "missing", "The matching bounded validation artifact is missing or ambiguous."
                else:
                    report = validate_artifact(await self.github.artifact_bytes(repo, artifacts[0]["id"]),
                        {"fix_run_id": run.id, "patch_hash": run.patch_hash, "head_sha": run.head_sha,
                         "run_id": validation.get("run_id"), "targets": self.manifest(run, project)["targets"]})
                    run.validation = ValidationResult(status=report["status"], summary=report["summary"],
                        run_url=validation.get("html_url"), details=report)
        if not pr.get("merged"):
            if run.validation.status == "passed":
                run.status = "checks_passed"
            elif run.validation.status in {"failed", "missing"}:
                run.status = "checks_failed"
        self.fixes.save(run)
