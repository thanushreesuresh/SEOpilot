"""One lifespan-owned worker, backed by a persisted SQLite queue."""

import asyncio
import logging
from collections.abc import Awaitable, Callable

from .models import Audit, Page, now
from .storage import Store

log = logging.getLogger(__name__)


async def execute(audit: Audit, store: Store):
    from .ai import enrich
    from .crawler import crawl
    from .rules import analyze, calculate_score, rule_recommendations

    async def progress(pages: list[Page], discovered: int):
        audit.pages = list(pages)
        audit.progress.visited = len(pages)
        audit.progress.discovered = discovered
        audit.progress.message = f"Checked {len(pages)} pages; {discovered} discovered"
        store.save(audit)

    result = await crawl(audit.url, audit.options, progress=progress)
    audit.pages = result.pages
    audit.warnings = result.warnings
    audit.coverage = result.coverage
    audit.status = "analyzing"
    audit.progress.stage = "analyzing"
    audit.progress.message = "Checking page evidence against SEO rules"
    store.save(audit)
    audit.issues = analyze(audit.pages, audit.origin, result.robots_state, result.sitemap_state)
    audit.score = calculate_score(audit.pages, audit.issues)
    audit.recommendations = rule_recommendations(audit.issues, audit.pages)
    audit.status = "reviewing"
    audit.progress.stage = "reviewing"
    audit.progress.message = "Preparing and reviewing recommendations"
    store.save(audit)
    try:
        await enrich(audit)
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


async def run_queue(store: Store, processor: Callable[[Audit, Store], Awaitable[None]] = execute):
    while True:
        audit = store.claim()
        if audit is None:
            await asyncio.sleep(0.3)
            continue
        try:
            await processor(audit, store)
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
