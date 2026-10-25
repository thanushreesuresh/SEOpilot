"""Loopback-only API for the single-user SEOPilot demo."""

import asyncio
import os
import time
from collections import deque
from contextlib import asynccontextmanager, suppress
from functools import partial
from pathlib import Path
from uuid import UUID

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .abuse import client_identity, is_loopback_client
from .models import Audit, AuditRequest, AuditSummary, DecisionRequest, Progress, Recommendation, UsageStatus
from .runner import execute, run_queue
from .settings import BACKEND_ROOT, Settings, proxy_token
from .storage import Store

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
ALLOWED_ORIGINS = {"http://localhost:3000", "http://127.0.0.1:3000"}
MAX_BODY = 16384


def create_app(db_path: str | Path | None = None, *, start_worker: bool = True, processor=None, settings: Settings | None = None, github_client=None) -> FastAPI:
    path = db_path or os.environ.get("SEOPILOT_DB") or Path(__file__).resolve().parents[1] / ".data" / "seopilot.db"
    # No database or worker is created merely by importing the OpenAPI definition.
    starts: deque[float] = deque()
    config = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.store = Store(path)
        # Tests with explicit databases get an isolated token beside that database.
        token_path = Path(os.environ.get("SEOPILOT_PROXY_TOKEN_FILE") or
                          (Path(path).parent / "proxy-token" if db_path else BACKEND_ROOT / ".data" / "proxy-token"))
        app.state.proxy_token = proxy_token(token_path)
        app.state.store.recover()
        from .fix_api import initialize
        from .fix_engine import FixEngine

        initialize(app, github_client)
        app.state.fix_engine = FixEngine(app.state.store, app.state.github, app.state.fix_lock)
        app.state.store.fixes.cleanup()
        task = asyncio.create_task(run_queue(app.state.store, processor=processor or partial(execute, settings=config),
                                            fix_tick=app.state.fix_engine.tick)) if start_worker else None
        app.state.worker = task
        yield
        if task:
            task.cancel()
            with suppress(asyncio.CancelledError, RuntimeError):
                await task
        await app.state.github.close()

    app = FastAPI(title="SEOPilot", version="0.2.0", lifespan=lifespan)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1"])

    @app.middleware("http")
    async def guard(request: Request, call_next):
        try:
            request.state.identity = client_identity(request)
            request.state.unlimited_audits = config.local_unlimited_audits and is_loopback_client(request)
        except HTTPException as exc:
            return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
        if request.method in ("POST", "PATCH", "PUT", "DELETE"):
            origin = request.headers.get("origin")
            if origin and origin not in ALLOWED_ORIGINS:
                return JSONResponse({"detail": "This local API does not accept requests from that origin."}, status_code=403)
            if request.headers.get("sec-fetch-site") == "cross-site":
                return JSONResponse({"detail": "Cross-site requests are not permitted."}, status_code=403)
            if request.headers.get("content-type", "").split(";")[0] != "application/json":
                return JSONResponse({"detail": "Use application/json."}, status_code=415)
            size = 0
            chunks = []
            async for chunk in request.stream():
                size += len(chunk)
                if size > MAX_BODY:
                    return JSONResponse({"detail": "Request is too large."}, status_code=413)
                chunks.append(chunk)
            request._body = b"".join(chunks)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        return response

    def admit(request: Request):
        if request.state.unlimited_audits:
            return
        tick = time.monotonic()
        while starts and tick - starts[0] >= 60:
            starts.popleft()
        if len(starts) >= 10:
            raise HTTPException(429, "Too many audit requests. Please wait a minute.", headers={"Retry-After": "60"})
        starts.append(tick)

    @app.get("/api/health")
    async def health(request: Request):
        task = request.app.state.worker
        if task is not None and task.done():
            # Read the exception so failed background tasks never appear healthy.
            if not task.cancelled():
                task.exception()
            raise HTTPException(503, "The audit worker stopped. Restart the local API.")
        return {"status": "ok", "mode": "local-single-user"}

    @app.get("/api/usage", response_model=UsageStatus)
    async def usage(request: Request):
        store = request.app.state.store
        ai_ready = config.ai_enabled and bool(os.getenv("OPENAI_API_KEY", "").strip()) and os.getenv("OPENAI_MODEL", "gpt-6-luna").strip() == "gpt-6-luna"
        return UsageStatus(**store.quota(request.state.identity, unlimited=request.state.unlimited_audits), ai_enabled=ai_ready,
                           ai_calls_remaining=store.ai_calls_remaining(config.ai_daily_call_limit))

    @app.post("/api/audits", response_model=Audit, status_code=202)
    async def start_audit(body: AuditRequest, request: Request, response: Response):
        from .network import normalize_url, origin_of

        try:
            url = normalize_url(body.url)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        admit(request)
        if request.app.state.worker is not None and request.app.state.worker.done():
            raise HTTPException(503, "The audit worker stopped. Restart the local API.")
        audit = Audit(url=url, origin=origin_of(url), options=body.options,
                      allow_ai=body.allow_ai, business_context=body.business_context,
                      progress=Progress(limit=body.options.page_limit))
        admitted, reason, quota = request.app.state.store.admit_audit(
            audit, request.state.identity, unlimited=request.state.unlimited_audits)
        headers = {} if request.state.unlimited_audits else {
            "RateLimit-Limit": "3", "RateLimit-Remaining": str(quota["remaining"])}
        if reason == "daily":
            raise HTTPException(429, "Daily audit allowance reached: 3 audits per rolling 24 hours. Try again after the reset.",
                                headers={**headers, "Retry-After": str(quota["retry_after"])})
        if reason == "queue":
            raise HTTPException(429, "The local audit queue is full. Wait for an audit to finish.",
                                headers={**headers, "Retry-After": "30"})
        for name, value in headers.items():
            response.headers[name] = value
        response.headers["X-Audit-Reused"] = str(reason == "reused").lower()
        return admitted

    @app.get("/api/audits", response_model=list[AuditSummary])
    async def history(request: Request):
        return request.app.state.store.history()

    @app.get("/api/audits/{audit_id}", response_model=Audit)
    async def get_audit(audit_id: str, request: Request):
        audit = request.app.state.store.get(audit_id)
        if not audit:
            raise HTTPException(404, "Audit not found")
        return audit

    @app.patch("/api/recommendations/{recommendation_id}/decision", response_model=Recommendation)
    async def decide(recommendation_id: str, body: DecisionRequest, request: Request):
        try:
            recommendation = request.app.state.store.decide(recommendation_id, body.status)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from None
        if not recommendation:
            raise HTTPException(404, "Recommendation not found")
        return recommendation

    @app.post("/api/audits/{audit_id}/cancel", response_model=Audit)
    async def cancel_audit(audit_id: UUID, request: Request):
        try:
            audit = request.app.state.store.cancel_audit(str(audit_id))
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from None
        if audit is None:
            raise HTTPException(404, "Audit not found")
        return audit

    @app.post("/api/demo-audits", response_model=Audit, status_code=201)
    async def demo(request: Request):
        from .demo import build_demo

        admit(request)
        # Current fixtures are free/offline; old snapshots and decisions remain.
        audit = await build_demo()
        return request.app.state.store.get_or_create_demo(audit)

    from .fix_api import router

    app.include_router(router())
    from .reporting_api import reporting_router

    app.include_router(reporting_router())
    return app


app = create_app()
