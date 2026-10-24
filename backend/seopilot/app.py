"""Loopback-only API for the single-user SEOPilot demo."""

import asyncio
import os
import time
from collections import deque
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .models import Audit, AuditRequest, AuditSummary, DecisionRequest, Progress, Recommendation
from .runner import run_queue
from .storage import Store

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
ALLOWED_ORIGINS = {"http://localhost:3000", "http://127.0.0.1:3000"}
MAX_BODY = 16384


def create_app(db_path: str | Path | None = None, *, start_worker: bool = True, processor=None) -> FastAPI:
    path = db_path or os.environ.get("SEOPILOT_DB") or Path(__file__).resolve().parents[1] / ".data" / "seopilot.db"
    # No database or worker is created merely by importing the OpenAPI definition.
    starts: deque[float] = deque()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.store = Store(path)
        app.state.store.recover()
        task = asyncio.create_task(run_queue(app.state.store, **({"processor": processor} if processor else {}))) if start_worker else None
        app.state.worker = task
        yield
        if task:
            task.cancel()
            with suppress(asyncio.CancelledError, RuntimeError):
                await task

    app = FastAPI(title="SEOPilot", version="0.1.0", lifespan=lifespan)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1"])

    @app.middleware("http")
    async def guard(request: Request, call_next):
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

    def admit():
        tick = time.monotonic()
        while starts and tick - starts[0] >= 60:
            starts.popleft()
        if len(starts) >= 10:
            raise HTTPException(429, "Too many audit requests. Please wait a minute.")
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

    @app.post("/api/audits", response_model=Audit, status_code=202)
    async def start_audit(body: AuditRequest, request: Request):
        from .network import normalize_url, origin_of

        try:
            url = normalize_url(body.url)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        admit()
        if request.app.state.worker is not None and request.app.state.worker.done():
            raise HTTPException(503, "The audit worker stopped. Restart the local API.")
        audit = Audit(url=url, origin=origin_of(url), options=body.options,
                      business_context=body.business_context, progress=Progress(limit=body.options.page_limit))
        if not request.app.state.store.enqueue(audit):
            raise HTTPException(429, "The local audit queue is full. Wait for an audit to finish.")
        return audit

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

    @app.post("/api/demo-audits", response_model=Audit, status_code=201)
    async def demo(request: Request):
        from .demo import build_demo

        admit()
        audit = await build_demo()
        request.app.state.store.save(audit)
        return audit

    return app


app = create_app()
