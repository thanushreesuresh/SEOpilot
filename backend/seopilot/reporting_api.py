"""Cost-free reports from stored evidence; these routes never enqueue work."""

import json
from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request

from .reporting_models import AuditComparison, AuditReport, ComparisonRequest


def reporting_router() -> APIRouter:
    api = APIRouter(prefix="/api")

    @api.post("/audit-comparisons", response_model=AuditComparison)
    async def compare(body: ComparisonRequest, request: Request):
        from .audit_reporting import compare_audits

        store = request.app.state.store
        before, after = store.get(str(body.before_audit_id)), store.get(str(body.after_audit_id))
        if before is None or after is None:
            raise HTTPException(404, "Audit not found")
        if before.id == after.id:
            raise HTTPException(409, "Choose two different audits.")
        try:
            if datetime.fromisoformat(before.created_at) >= datetime.fromisoformat(after.created_at):
                raise ValueError("Choose the earlier audit as the baseline.")
            return compare_audits(before, after)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from None

    @api.get("/audits/{audit_id}/report/{format}", response_model=AuditReport)
    async def report(audit_id: UUID, format: Literal["markdown", "csv", "json"], request: Request):
        from .audit_reporting import export_audit

        store = request.app.state.store
        audit = store.get(str(audit_id))
        if audit is None:
            raise HTTPException(404, "Audit not found")
        if audit.status not in {"completed", "partial", "failed", "interrupted", "cancelled"}:
            raise HTTPException(409, "Wait for the audit to finish before exporting a report.")
        try:
            history = [*store.decisions(audit.id), *[item.model_dump() for item in store.fixes.dispositions(audit.id)]]
            result = export_audit(audit, format=format, dispositions=history)
            if len(json.dumps(result, ensure_ascii=False).encode("utf-8")) > 1024*1024:
                raise ValueError("The report exceeds the 1 MiB export limit.")
            return result
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from None

    return api
