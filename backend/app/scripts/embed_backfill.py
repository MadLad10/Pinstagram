"""Embed every verified place and published review that is missing or stale.

    python -m app.scripts.embed_backfill

Safe to re-run: unchanged text is skipped by content hash. Run it after
seeding, and after switching EMBEDDING_MODEL (vectors from different models
can't be compared, so everything is re-embedded).
"""

import asyncio

from app.ai import get_embedder
from app.ai.indexing import embed_all
from app.db.session import AsyncSessionLocal


async def main() -> None:
    print(f"Embedding with {get_embedder().model} ...")
    async with AsyncSessionLocal() as db:
        total = await embed_all(db)
    print(f"Done: {total} places/reviews brought up to date.")


if __name__ == "__main__":
    asyncio.run(main())
