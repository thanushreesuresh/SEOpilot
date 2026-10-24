"""Shared API and persisted audit contracts. No credentials belong in these models."""

from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def new_id() -> str:
    return str(uuid4())


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


Severity = Literal["Critical", "High", "Medium", "Low"]
AuditStatus = Literal["queued", "crawling", "analyzing", "reviewing", "completed", "partial", "failed", "interrupted", "cancelled"]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_serialization_defaults_required=True)


class CrawlOptions(Contract):
    page_limit: int = Field(default=15, ge=1, le=30)
    max_depth: int = Field(default=2, ge=0, le=3)
    delay_ms: int = Field(default=750, ge=750, le=10000)
    timeout_seconds: float = Field(default=10, ge=1, le=10)
    response_bytes: int = Field(default=2097152, ge=1024, le=2097152)
    total_seconds: int = Field(default=120, ge=5, le=120)


class AuditRequest(Contract):
    url: str = Field(min_length=8, max_length=2048)
    business_context: str = Field(default="", max_length=2000)
    options: CrawlOptions = Field(default_factory=CrawlOptions)
    allow_ai: bool = True


class Heading(Contract):
    level: int = Field(ge=1, le=6)
    text: str


class ImageInfo(Contract):
    src: str
    alt: str | None = None


class StructuredObservation(Contract):
    code: str
    message: str
    block_index: int
    evidence: str


class StructuredDataSummary(Contract):
    blocks: int = Field(ge=0)
    types: list[str] = Field(default_factory=list, max_length=20)
    observations: list[StructuredObservation] = Field(default_factory=list, max_length=50)
    truncated: bool = False


class Page(Contract):
    id: str = Field(default_factory=new_id)
    url: str
    depth: int = 0
    status_code: int | None = None
    outcome: Literal["html", "http_error", "non_html", "blocked", "error"] = "html"
    content_type: str = "text/html"
    title: str = ""
    description: str = ""
    headings: list[Heading] = Field(default_factory=list)
    canonicals: list[str] = Field(default_factory=list)
    robots: list[str] = Field(default_factory=list)
    images: list[ImageInfo] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)
    text_excerpt: str = ""
    error: str | None = None
    truncated_fields: list[str] = Field(default_factory=list)
    structured_data: StructuredDataSummary | None = None


class Evidence(Contract):
    id: str = Field(default_factory=new_id)
    field: str
    value: str


class Issue(Contract):
    id: str = Field(default_factory=new_id)
    rule_id: str
    title: str
    url: str
    page_ids: list[str] = Field(default_factory=list)
    severity: Severity
    category: str
    explanation: str
    evidence: list[Evidence]
    recommended_fix: str
    estimated_impact: str = "Estimated improvement to clarity or crawlability; ranking outcomes are not guaranteed."
    source: Literal["deterministic"] = "deterministic"
    is_site: bool = False


class Recommendation(Contract):
    id: str = Field(default_factory=new_id)
    source: Literal["rule", "ai", "demo"] = "rule"
    kind: Literal["technical", "title", "description", "heading", "content", "keyword", "internal_link"] = "technical"
    title: str
    url: str
    page_id: str | None = None
    issue_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    rationale: str
    suggested_value: str | None = None
    priority: Severity
    status: Literal["pending", "approved", "rejected"] = "pending"
    decided_at: str | None = None
    basis: Literal["observed", "inferred"] = "observed"


class Coverage(Contract):
    attempted: int = 0
    assessed: int = 0
    blocked: int = 0
    failed: int = 0
    unchecked: int = 0
    truncated: bool = False


class DiscoveryProbe(Contract):
    kind: Literal["robots", "sitemap"]
    url: str = Field(max_length=2048)
    status_code: int | None = Field(default=None, ge=100, le=599)
    outcome: Literal["present", "absent", "blocked", "unknown"]
    explanation: str = Field(max_length=300)


class CrawlDiscovery(Contract):
    robots_state: Literal["present", "absent", "unknown"] = "unknown"
    sitemap_state: Literal["present", "absent", "unknown"] = "unknown"
    probes: list[DiscoveryProbe] = Field(default_factory=list, max_length=4)
    request_attempts: int = Field(default=0, ge=0, le=60)
    effective_delay_seconds: float = Field(default=0.75, ge=0.75, allow_inf_nan=False)
    notes: list[str] = Field(default_factory=list, max_length=5)


class Progress(Contract):
    stage: str = "queued"
    visited: int = 0
    discovered: int = 0
    limit: int = 15
    message: str = "Waiting to start"


class Score(Contract):
    version: str = "1"
    value: int | None = None
    assessed_pages: int = 0
    formula: str = "100 − mean(capped page penalties) − capped site penalties. Critical=20, High=10, Medium=5, Low=2; HTTP error pages=100. Site cap=20. Unknown pages excluded."


class Audit(Contract):
    id: str = Field(default_factory=new_id)
    url: str
    origin: str = ""
    mode: Literal["live", "demo"] = "live"
    status: AuditStatus = "queued"
    created_at: str = Field(default_factory=now)
    updated_at: str = Field(default_factory=now)
    completed_at: str | None = None
    business_context: str = ""
    allow_ai: bool = True
    options: CrawlOptions = Field(default_factory=CrawlOptions)
    progress: Progress = Field(default_factory=Progress)
    pages: list[Page] = Field(default_factory=list)
    issues: list[Issue] = Field(default_factory=list)
    recommendations: list[Recommendation] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    coverage: Coverage = Field(default_factory=Coverage)
    discovery: CrawlDiscovery | None = None
    score: Score = Field(default_factory=Score)
    ai_status: Literal["unavailable", "pending", "available", "failed", "demo", "limited", "cancelled"] = "unavailable"
    summary: str = ""
    rules_version: str = "1"
    verification_urls: list[str] = Field(default_factory=list, max_length=3)


class AuditSummary(Contract):
    id: str
    url: str
    mode: Literal["live", "demo"]
    status: AuditStatus
    created_at: str
    score: int | None
    pages: int
    issues: int


class DecisionRequest(Contract):
    status: Literal["approved", "rejected"]


class UsageStatus(Contract):
    limit: int = 3
    used: int
    remaining: int
    reset_at: str | None
    retry_after: int
    window_hours: int = 24
    ai_enabled: bool
    ai_calls_remaining: int
