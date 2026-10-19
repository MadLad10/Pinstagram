"""Keeps place and review embeddings in sync with the source rows.

The tables themselves are the job queue: a verified place or published review
is stale when it has no embedding, was embedded with a different model, or was
updated after it was embedded. `embed_pending()` processes one batch; the
background worker (app.ai.worker) calls it in a loop, and
`python -m app.scripts.embed_backfill` drains the queue from a shell.
"""

import hashlib
import logging

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import get_embedder
from app.models.embedding import PlaceEmbedding, ReviewEmbedding

log = logging.getLogger(__name__)

# Only one API instance embeds at a time.
_ADVISORY_LOCK_KEY = 0x50_49_4E_53  # "PINS"


def place_document(row) -> str:
    """The text a place is embedded as. Mirrors what users search for: what it
    is, where it is, what it has, and how it's described."""
    parts = [f"{row['name']}. {row['category']} in {row['area'] or row['district']}."]
    if row["price_tier"]:
        parts.append(f"Price: {row['price_tier']}.")
    if row["amenities"]:
        parts.append(
            "Amenities: "
            + ", ".join(a.replace("_", " ") for a in row["amenities"])
            + "."
        )
    if row["description"]:
        parts.append(row["description"])
    return " ".join(parts)


def content_hash(model: str, doc: str) -> str:
    return hashlib.sha256(f"{model}\n{doc}".encode()).hexdigest()


async def _cleanup(db: AsyncSession) -> None:
    """Drop embeddings whose source is no longer public."""
    await db.execute(
        text("""
        DELETE FROM review_embeddings re USING reviews r
        WHERE r.id = re.review_id AND r.status <> 'published'
        """)
    )
    await db.execute(
        text("""
        DELETE FROM place_embeddings pe USING places p
        WHERE p.id = pe.place_id AND NOT p.is_verified
        """)
    )


async def _sync(db: AsyncSession, rows, model, table, key, make_doc, extra=None) -> int:
    """Embed the rows whose text changed; just re-stamp the ones that didn't."""
    if not rows:
        return 0
    docs = [make_doc(r) for r in rows]
    hashes = [content_hash(model, d) for d in docs]
    todo = [i for i, r in enumerate(rows) if r["old_hash"] != hashes[i]]
    vectors = {}
    if todo:
        embedded = await get_embedder().embed(
            [docs[i] for i in todo], kind="document", purpose="embed_documents"
        )
        vectors = dict(zip(todo, embedded, strict=True))

    for i, row in enumerate(rows):
        values = {
            key: row["id"],
            "model": model,
            "content_hash": hashes[i],
            "source_updated_at": row["updated_at"],
            **(extra(row) if extra else {}),
        }
        if i in vectors:
            values["embedding"] = vectors[i]
            stmt = insert(table).values(**values)
            stmt = stmt.on_conflict_do_update(
                index_elements=[key],
                set_={k: v for k, v in values.items() if k != key},
            )
        else:  # same text and model: only the timestamp moves
            stmt = (
                table.__table__.update()
                .where(table.__table__.c[key] == row["id"])
                .values(source_updated_at=row["updated_at"])
            )
        await db.execute(stmt)
    return len(rows)


async def embed_pending(db: AsyncSession, batch_size: int = 32) -> int:
    """Process up to `batch_size` stale places and reviews. Returns how many
    rows were brought up to date (0 means the queue is empty)."""
    # Transaction-scoped, so it can't leak on a pooled connection; another
    # instance already working means there's nothing for us to do.
    locked = (
        await db.execute(
            text("SELECT pg_try_advisory_xact_lock(:k)"), {"k": _ADVISORY_LOCK_KEY}
        )
    ).scalar()
    if not locked:
        return 0
    model = get_embedder().model
    await _cleanup(db)

    places = (
        (
            await db.execute(
                text("""
            SELECT p.id, p.name, p.category::text AS category, p.area, p.district,
                   p.price_tier::text AS price_tier, p.amenities, p.description,
                   p.updated_at, pe.content_hash AS old_hash
            FROM places p
            LEFT JOIN place_embeddings pe ON pe.place_id = p.id
            WHERE p.is_verified
              AND (pe.place_id IS NULL OR pe.model <> :model
                   OR pe.source_updated_at < p.updated_at)
            ORDER BY p.updated_at
            LIMIT :n
            """),
                {"model": model, "n": batch_size},
            )
        )
        .mappings()
        .all()
    )
    done = await _sync(db, places, model, PlaceEmbedding, "place_id", place_document)

    reviews = (
        (
            await db.execute(
                text("""
            SELECT r.id, r.place_id, r.body, r.updated_at,
                   re.content_hash AS old_hash
            FROM reviews r
            JOIN places p ON p.id = r.place_id AND p.is_verified
            LEFT JOIN review_embeddings re ON re.review_id = r.id
            WHERE r.status = 'published'
              AND (re.review_id IS NULL OR re.model <> :model
                   OR re.source_updated_at < r.updated_at)
            ORDER BY r.updated_at
            LIMIT :n
            """),
                {"model": model, "n": batch_size},
            )
        )
        .mappings()
        .all()
    )
    done += await _sync(
        db,
        reviews,
        model,
        ReviewEmbedding,
        "review_id",
        lambda r: r["body"],
        extra=lambda r: {"place_id": r["place_id"]},
    )
    await db.commit()
    return done


async def embed_all(db: AsyncSession, batch_size: int = 32) -> int:
    total = 0
    while n := await embed_pending(db, batch_size):
        total += n
    return total
