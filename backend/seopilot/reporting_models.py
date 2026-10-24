"""Credential-free, read-only audit reporting contracts."""

from typing import Literal
from uuid import UUID

from .models import Contract, Coverage


class ComparisonRequest(Contract):
    before_audit_id: UUID
    after_audit_id: UUID


class FindingChange(Contract):
    stable_id: str
    rule_id: str
    url: str
    field: str
    title: str
    severity: str
    reason: str
    is_site: bool
    before_issue_ids: list[str]
    after_issue_ids: list[str]
    status: Literal["added", "persistent", "resolved", "unresolved_unknown"]
    after_state: Literal["assessed", "blocked", "unchecked", "unknown"]


class ChangeCounts(Contract):
    added: int
    persistent: int
    resolved: int
    unresolved_unknown: int


class AuditComparison(Contract):
    before_audit_id: str
    after_audit_id: str
    origin: str
    rules_version_before: str
    rules_version_after: str
    score_version_before: str
    score_version_after: str
    versions_match: bool
    assessed_urls_before: list[str]
    assessed_urls_after: list[str]
    common_assessed_urls: list[str]
    added_assessed_urls: list[str]
    removed_assessed_urls: list[str]
    coverage_before: Coverage
    coverage_after: Coverage
    coverage_comparable: bool
    score_before: int | None
    score_after: int | None
    score_delta: int | None
    score_delta_reason: str
    added: list[FindingChange]
    persistent: list[FindingChange]
    resolved: list[FindingChange]
    unresolved_unknown: list[FindingChange]
    counts: ChangeCounts
    limitations: list[str]


class AuditReport(Contract):
    filename: str
    media_type: str
    content: str
