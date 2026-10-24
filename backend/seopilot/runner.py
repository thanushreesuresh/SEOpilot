"""One lifespan-owned worker, backed by a persisted SQLite queue."""

import asyncio
import logging
import sqlite3
from collections.abc import Awaitable, Callable
from contextlib import suppress

from .models import Audit, Page, now
from .settings import Settings
from .storage import Store

log = logging.getLogger(__name__)


async def execute(audit: Audit, store: Store, *, settings: Settings | None = None):
    from .crawler import crawl
    from .rules import RULES_VERSION, analyze, calculate_score, rule_recommendations

    async def progress(pages: list[Page], discovered: int):
        audit.pages = list(pages)
        audit.progress.visited = len(pages)
        audit.progress.discovered = discovered
        audit.progress.message = f"Checked {len(pages)} pages; {discovered} discovered"
        store.save(audit)

    if audit.verification_urls:
        result = await crawl(audit.url, audit.options, progress=progress, targets=audit.verification_urls)
    else:
        result = await crawl(audit.url, audit.options, progress=progress)
    audit.pages = result.pages
    audit.warnings = result.warnings
    audit.coverage = result.coverage
    audit.status = "analyzing"
    audit.progress.stage = "analyzing"
    audit.progress.message = "Checking page evidence against SEO rules"
    store.save(audit)
    audit.issues = analyze(audit.pages, audit.origin, result.robots_state, result.sitemap_state,
                           discovery_evidence=result.discovery_evidence)
    audit.rules_version = RULES_VERSION
    audit.score = calculate_score(audit.pages, audit.issues)
    audit.recommendations = rule_recommendations(audit.issues, audit.pages)
    audit.status = "reviewing"
    audit.progress.stage = "reviewing"
    audit.progress.message = "Preparing and reviewing recommendations"
    store.save(audit)
    try:
        from .ai import enrich

        await enrich(audit, store=store, settings=settings)
    except Exception:
        # Provider bugs must never discard a completed deterministic audit.
        log.warning("AI enrichment failed for audit %s", audit.id)
        audit.ai_status = "failed"
        audit.warnings.append("AI recommendations could not be completed. Rule-based recommendations remain available.")
    assessed = audit.coverage.assessed
    audit.status = "partial" if audit.warnings or audit.coverage.truncated or audit.coverage.failed or audit.coverage.blocked else "completed"
    if assessed == 0:
        audit.status = "failed"
    audit.completed_at = now()
    audit.progress.stage = audit.status
    audit.progress.visited = len(audit.pages)
    audit.progress.message = "Audit finished" if assessed else "No pages could be assessed. Review the coverage details."
    if not audit.summary:
        audit.summary = f"Assessed {assessed} pages and found {len(audit.issues)} observations. Review higher-priority actions first."
    store.save(audit)


async def _process_audit(audit: Audit, store: Store, processor):
    task = asyncio.ensure_future(processor(audit, store))
    try:
        while not task.done():
            if store.is_cancelled(audit.id):
                task.cancel()
                break
            await asyncio.wait({task}, timeout=0.3)
        try:
            await task
        except asyncio.CancelledError:
            # Cancelling this child must not swallow lifespan/server shutdown.
            if asyncio.current_task().cancelling() or not store.is_cancelled(audit.id):
                raise
    finally:
        if not task.done():
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task


async def run_queue(store: Store, processor: Callable[[Audit, Store], Awaitable[None]] = execute, fix_tick=None):
    claim_failures = 0
    while True:
        try:
            audit = store.claim()
            claim_failures = 0
        except sqlite3.OperationalError:
            claim_failures += 1
            log.warning("Audit queue temporarily unavailable; retrying claim")
            if claim_failures >= 3:
                raise RuntimeError("Audit queue storage unavailable") from None
            await asyncio.sleep(0.5 * claim_failures)
            continue
        if audit is None:
            if fix_tick is not None:
                await fix_tick()
            await asyncio.sleep(0.3)
            continue
        try:
            await _process_audit(audit, store, processor)
        except asyncio.CancelledError:
            audit.status = "interrupted"
            audit.progress.stage = "interrupted"
            audit.progress.message = "Server stopped; start a new audit to retry."
            store.save(audit)
            raise
        except Exception:
            log.warning("Audit %s failed during %s", audit.id, audit.progress.stage)
            audit.status = "failed"
            audit.progress.stage = "failed"
            audit.progress.message = "The audit could not finish. Retry or inspect another permitted website."
            audit.warnings.append("Audit failed safely; any collected page evidence is preserved.")
            audit.completed_at = now()
            store.save(audit)
