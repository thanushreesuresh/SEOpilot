import asyncio
import sqlite3

import pytest

from seopilot.models import Audit
from seopilot.runner import run_queue
from seopilot.storage import Store


@pytest.mark.asyncio
async def test_worker_recovers_from_one_transient_claim_failure(tmp_path):
    store = Store(tmp_path / "queue.db")
    audit = Audit(url="https://example.com/")
    store.enqueue(audit)
    real_claim = store.claim
    attempts = 0
    finished = asyncio.Event()

    def claim():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise sqlite3.OperationalError("database locked")
        return real_claim()

    async def process(item, repository):
        item.status = "completed"
        repository.save(item)
        finished.set()

    store.claim = claim
    worker = asyncio.create_task(run_queue(store, process))
    try:
        await asyncio.wait_for(finished.wait(), 3)
        assert attempts >= 2
        assert store.get(audit.id).status == "completed"
    finally:
        worker.cancel()
        with pytest.raises(asyncio.CancelledError):
            await worker


@pytest.mark.asyncio
async def test_worker_preserves_failure_as_a_reportable_stop(tmp_path):
    store = Store(tmp_path / "queue.db")

    def fail():
        raise sqlite3.OperationalError("database unavailable")

    store.claim = fail
    with pytest.raises(RuntimeError, match="storage unavailable"):
        await asyncio.wait_for(run_queue(store), 3)
