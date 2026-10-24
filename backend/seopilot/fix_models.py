"""Public v2 contracts. Source contents and credentials never enter API models."""

from datetime import datetime, timedelta, timezone
from typing import Literal

from pydantic import Field

from .models import Contract, new_id, now


def poll_deadline() -> str:
    return (datetime.now(timezone.utc)+timedelta(minutes=10)).isoformat()


class RepositoryInfo(Contract):
    id: int
    installation_id: int
    owner: str
    name: str
    default_branch: str


class ConnectionCheck(Contract):
    setting: Literal["GITHUB_APP_ID", "GITHUB_APP_PRIVATE_KEY_PATH", "GITHUB_APP_OWNERS"]
    present: bool


class ConnectionStatus(Contract):
    configured: bool
    message: str
    state: Literal["unknown", "setup_required", "ready", "no_repositories", "credentials_error",
                   "access_denied", "rate_limited", "unavailable"] = "unknown"
    setup_checks: list[ConnectionCheck] = Field(default_factory=list, max_length=3)
    checked_at: str | None = None
    repositories: list[RepositoryInfo] = Field(default_factory=list)
    publication_limit: int = 2
    publications_remaining: int = 2
    actions_notice: str = "Publishing a branch or PR can run repository CI and preview automation. GitHub Actions usage is separate from OpenAI usage."


class ProjectRequest(Contract):
    name: str = Field(min_length=1, max_length=100)
    production_origin: str = Field(min_length=8, max_length=2048)
    installation_id: int = Field(gt=0)
    repository_id: int = Field(gt=0)
    base_branch: str = Field(min_length=1, max_length=200)
    app_subdirectory: str = Field(default="", max_length=200)
    workflow: str = Field(default="seopilot-validation.yml", pattern=r"^[A-Za-z0-9_-]+\.ya?ml$")
    confirms_ownership: Literal[True]


class Project(Contract):
    id: str = Field(default_factory=new_id)
    name: str
    production_origin: str
    installation_id: int
    repository_id: int
    repository_owner: str
    repository_name: str
    base_branch: str
    app_subdirectory: str = ""
    workflow: str = "seopilot-validation.yml"
    connected: bool = True
    confirmed_at: str = Field(default_factory=now)


class MetadataEdit(Contract):
    url: str = Field(min_length=8, max_length=2048)
    title: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, min_length=1, max_length=320)
    recommendation_ids: list[str] = Field(default_factory=list, max_length=2)


class FixRequest(Contract):
    project_id: str
    audit_id: str
    edits: list[MetadataEdit] = Field(min_length=1, max_length=3)


class FixTarget(Contract):
    url: str
    route: str
    path: str
    old_title: str | None = None
    old_description: str | None = None
    title: str | None = None
    description: str | None = None
    canonical: list[str] = Field(default_factory=list)
    robots: list[str] = Field(default_factory=list)


FixStatus = Literal["preparing", "proposed", "publishing", "pr_opened", "checks_passed", "checks_failed", "merged", "awaiting_deployment", "live_verified", "verification_failed", "cancelled", "expired", "conflict", "failed"]


class ValidationResult(Contract):
    status: str = "pending"
    summary: str = "Validation has not completed."
    run_url: str | None = None
    details: dict = Field(default_factory=dict)


class FixRun(Contract):
    id: str = Field(default_factory=new_id)
    project_id: str
    audit_id: str
    repository_id: int
    base_branch: str
    base_sha: str
    patch_hash: str
    created_at: str = Field(default_factory=now)
    updated_at: str = Field(default_factory=now)
    expires_at: str
    status: FixStatus = "proposed"
    targets: list[FixTarget]
    changed_files: list[str]
    changed_lines: int
    branch: str = ""
    head_sha: str | None = None
    pr_number: int | None = None
    pr_url: str | None = None
    message: str = "Review the complete diff before approving publication."
    validation: ValidationResult = Field(default_factory=ValidationResult)
    verification: dict = Field(default_factory=dict)
    verification_audit_id: str | None = None
    source_purged: bool = False
    poll_until: str = Field(default_factory=poll_deadline)


class PatchExport(Contract):
    filename: str
    patch: str
    patch_hash: str


class PublishRequest(Contract):
    patch_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    confirms_publication: Literal[True]


class DispositionRequest(Contract):
    status: Literal["intentional", "dismissed", "open"]
    reason: str = Field(min_length=3, max_length=1000)


class FindingDisposition(Contract):
    audit_id: str
    issue_id: str
    rule_id: str
    url: str
    status: str
    reason: str
    recorded_at: str = Field(default_factory=now)
