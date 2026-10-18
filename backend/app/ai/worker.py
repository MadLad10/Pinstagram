"""Background AI work, run as a task inside the API process (Render's free
plan has no separate worker): keep embeddings in sync, then refresh stale
review summaries. Every step is idempotent and driven by database state, so
a restart or a second instance never loses or duplicates work."""

import asyncio
import logging

from app.ai.indexing import embed_all
from app.core.config import settings
from app.db.session import AsyncSessionLocal

log = logging.getLogger(__name__)

MAX_BACKOFF_S = 15 * 60
_wake: asyncio.Event | None = None


def wake() -> None:
    """Run now instead of at the next interval, e.g. right after a review is
    approved. A no-op when the worker isn't running (tests, scripts)."""
    if _wake is not None:
        _wake.set()


async def run_once() -> tuple[int, int]:
    from app.services import summary_service

    async with AsyncSessionLocal() as db:
        embedded = await embed_all(db)
        summarized = await summary_service.refresh_stale(db)
    return embedded, summarized


async def run_worker() -> None:
    global _wake
    _wake = asyncio.Event()
    delay = settings.AI_WORKER_INTERVAL_S
    while True:
        _wake.clear()
        try:
            embedded, summarized = await run_once()
            if embedded or summarized:
                log.info("AI worker: %d embedded, %d summaries", embedded, summarized)
            delay = settings.AI_WORKER_INTERVAL_S
            if summarized:
                delay = min(delay, 5)  # more summaries may be waiting
        except asyncio.CancelledError:
            raise
        except Exception:
            # Provider down or rate limited: keep the API up and retry later.
            delay = min(delay * 2, MAX_BACKOFF_S)
            log.warning("AI worker failed; retrying in %ss", delay, exc_info=True)
        try:
            await asyncio.wait_for(_wake.wait(), timeout=delay)
        except TimeoutError:
            pass
