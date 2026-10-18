"""Review summaries: pros, cons and "best for", grounded in a place's reviews.

Grounding is enforced in code, not just requested in the prompt:

1. The model only sees the place's published reviews, labelled R1..Rn, and
   must cite labels for every point.
2. `ground()` drops any point that cites nothing, cites a label that wasn't
   shown, mentions a number the cited reviews don't contain (prices and
   times are the most common inventions), or shares no content word with the
   cited reviews.

Summaries are cached in `review_summaries` and regenerated in the background
(see app.ai.worker) once REGENERATE_AFTER new reviews are published, or as soon
as a review they were built from is unpublished.
"""

import json
import logging
import re
import uuid

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import get_llm
from app.ai.types import LLMError, LLMRateLimited
from app.core.config import settings
from app.models.place import Place
from app.models.review import Review
from app.models.review_summary import ReviewSummary
from app.schemas.summary import ReviewSummaryRead, SummaryPoint

log = logging.getLogger(__name__)

MIN_REVIEWS = 3
REGENERATE_AFTER = 3
MAX_REVIEWS = 40  # most recent; keeps prompts small on free tiers
MAX_POINTS = 4
MAX_POINT_CHARS = 160
SECTIONS = ("pros", "cons", "best_for")

SYSTEM_PROMPT = """You summarize visitor reviews of one place for a travel app in Bangladesh.

Rules:
- Use ONLY what the reviews below state. Do not use outside knowledge, the
  place's name or category, or assumptions to add anything.
- Every point must cite the labels of the reviews that state it, e.g. ["R2", "R5"].
- Keep each point short (under 15 words) and specific. Prefer details several
  reviews agree on. If reviews disagree, say so in the point.
- Never invent prices, times, dishes or amenities. Copy numbers exactly.
- A section with nothing supported by the reviews must be an empty list.

Reply with JSON only, in this shape:
{"pros": [{"point": "...", "reviews": ["R1"]}],
 "cons": [{"point": "...", "reviews": ["R2"]}],
 "best_for": [{"point": "who or what it suits, e.g. Working on a laptop", "reviews": ["R3"]}]}"""

# Words too generic to show that a review supports a claim.
_GENERIC = {
    "about", "also", "around", "best", "better", "good", "great", "lovely",
    "nice", "people", "place", "really", "some", "spot", "that", "there",
    "they", "this", "very", "visit", "visitors", "with", "worth", "your",
    "reviewers", "review", "reviews", "mentioned", "several", "many", "most",
    "overall", "generally", "quite", "well",
}  # fmt: skip


class SummaryError(Exception):
    pass


def _stems(text: str) -> set[str]:
    words = re.findall(r"[a-z]+", text.lower())
    return {w[:5] for w in words if len(w) >= 4 and w not in _GENERIC}


def _numbers(text: str) -> set[str]:
    return set(re.findall(r"\d+", text))


def _labels(raw) -> list[str]:
    if not isinstance(raw, list):
        raw = [raw]
    out = []
    for item in raw:
        m = re.fullmatch(r"\[?\s*R?(\d+)\s*\]?", str(item).strip(), re.IGNORECASE)
        if m:
            out.append(f"R{int(m.group(1))}")
    return out


def supported(point: str, sources: list[str]) -> bool:
    source_text = " ".join(sources)
    if not _numbers(point) <= _numbers(source_text):
        return False
    claim = _stems(point)
    return bool(claim) and bool(claim & _stems(source_text))


def ground(raw: str, reviews: dict[str, str]) -> tuple[dict[str, list[dict]], int]:
    """Parse the model's JSON and keep only cited, supported points.

    Returns ({section: [{"text", "labels"}]}, number of points dropped)."""
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw)  # tolerate code fences
    try:
        data = json.loads(raw)
    except ValueError as exc:
        raise SummaryError(f"model did not return JSON: {raw[:200]!r}") from exc
    if not isinstance(data, dict):
        raise SummaryError("model returned JSON that isn't an object")

    out: dict[str, list[dict]] = {}
    dropped = 0
    for section in SECTIONS:
        items = data.get(section) or []
        kept: list[dict] = []
        seen: set[str] = set()
        for item in items if isinstance(items, list) else []:
            if not isinstance(item, dict):
                dropped += 1  # a bare string has no citations
                continue
            text_ = " ".join(str(item.get("point") or item.get("text") or "").split())
            labels = [
                label
                for label in _labels(
                    item.get("reviews") or item.get("review_ids") or []
                )
                if label in reviews
            ]
            labels = list(dict.fromkeys(labels))
            if (
                not text_
                or len(text_) > MAX_POINT_CHARS
                or not labels
                or not supported(text_, [reviews[label] for label in labels])
            ):
                dropped += 1
                log.info("Dropped ungrounded summary point: %r %r", text_, labels)
                continue
            if text_.lower() in seen:
                continue
            seen.add(text_.lower())
            kept.append({"text": text_, "labels": labels})
        out[section] = kept[:MAX_POINTS]
    return out, dropped


async def _published(db: AsyncSession, place_id: uuid.UUID) -> list[Review]:
    return list(
        (
            await db.execute(
                select(Review)
                .where(Review.place_id == place_id, Review.status == "published")
                .order_by(Review.created_at.desc(), Review.id)
                .limit(MAX_REVIEWS)
            )
        ).scalars()
    )


def _prompt(place: Place, reviews: dict[str, Review]) -> str:
    lines = [
        f"Place: {place.name} ({place.category}, {place.area or place.district})",
        "",
        "Reviews:",
    ]
    for label, review in reviews.items():
        body = " ".join(review.body.split())
        lines.append(f"[{label}] ({review.rating}/5) {body}")
    return "\n".join(lines)


async def generate_summary(
    db: AsyncSession, place_id: uuid.UUID
) -> ReviewSummary | None:
    """Summarize now and store the result. Returns None (and removes any old
    summary) when the place has too few published reviews."""
    place = await db.get(Place, place_id)
    if place is None:
        return None
    reviews = await _published(db, place_id)
    if len(reviews) < MIN_REVIEWS:
        await db.execute(
            delete(ReviewSummary).where(ReviewSummary.place_id == place_id)
        )
        await db.commit()
        return None

    labelled = {f"R{i}": r for i, r in enumerate(reviews, start=1)}
    llm = get_llm()
    result = await llm.chat(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _prompt(place, labelled)},
        ],
        purpose="review_summary",
        json_mode=True,
        temperature=0,
    )
    sections, dropped = ground(
        result.content, {label: r.body for label, r in labelled.items()}
    )

    def points(section: str) -> list[dict]:
        return [
            {
                "text": p["text"],
                "review_ids": [str(labelled[label].id) for label in p["labels"]],
            }
            for p in sections[section]
        ]

    values = {
        "pros": points("pros"),
        "cons": points("cons"),
        "best_for": points("best_for"),
        "review_ids": [r.id for r in reviews],
        "model": result.model or llm.model,
        "dropped_points": dropped,
        "generated_at": func.now(),
    }
    stmt = insert(ReviewSummary).values(place_id=place_id, **values)
    await db.execute(
        stmt.on_conflict_do_update(index_elements=["place_id"], set_=values)
    )
    await db.commit()
    return await db.get(ReviewSummary, place_id, populate_existing=True)


_STALE_SQL = """
    WITH counts AS (
        SELECT place_id, count(*) AS n FROM reviews
        WHERE status = 'published' GROUP BY place_id
    )
    SELECT p.id
    FROM places p
    JOIN counts c ON c.place_id = p.id
    LEFT JOIN review_summaries s ON s.place_id = p.id
    WHERE p.is_verified AND c.n >= :min_reviews AND (
        s.place_id IS NULL
        -- enough reviews published since the summary was written
        OR (SELECT count(*) FROM reviews r
            WHERE r.place_id = p.id AND r.status = 'published'
              AND r.updated_at > s.generated_at
              AND NOT (r.id = ANY(s.review_ids))) >= :regenerate_after
        -- a review it was built from has been edited, rejected or deleted
        OR EXISTS (
            SELECT 1 FROM unnest(s.review_ids) AS used(id)
            WHERE NOT EXISTS (
                SELECT 1 FROM reviews r
                WHERE r.id = used.id AND r.status = 'published'
                  AND r.updated_at <= s.generated_at))
    )
"""


async def stale_place_ids(
    db: AsyncSession, limit: int | None = None
) -> list[uuid.UUID]:
    sql = _STALE_SQL + " ORDER BY s.generated_at NULLS FIRST, p.id"
    params = {"min_reviews": MIN_REVIEWS, "regenerate_after": REGENERATE_AFTER}
    if limit is not None:
        sql += " LIMIT :limit"
        params["limit"] = limit
    return list((await db.execute(text(sql), params)).scalars())


async def refresh_stale(db: AsyncSession, limit: int = 3) -> int:
    """Regenerate up to `limit` stale summaries and drop summaries for places
    that fell below MIN_REVIEWS. Small batches keep free-tier quotas safe."""
    await db.execute(
        text("""
        DELETE FROM review_summaries s
        WHERE (SELECT count(*) FROM reviews r
               WHERE r.place_id = s.place_id AND r.status = 'published') < :min
        """),
        {"min": MIN_REVIEWS},
    )
    await db.commit()
    done = 0
    for place_id in await stale_place_ids(db, limit):
        try:
            await generate_summary(db, place_id)
            done += 1
        except LLMRateLimited:
            log.warning("Rate limited; pausing review summaries")
            break
        except (LLMError, SummaryError) as exc:
            await db.rollback()
            log.warning("Summary for place %s failed: %s", place_id, exc)
    return done


async def get_summary(db: AsyncSession, place_id: uuid.UUID) -> ReviewSummaryRead:
    exists = await db.scalar(
        select(Place.id).where(Place.id == place_id, Place.is_verified.is_(True))
    )
    if not exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Place not found"
        )

    summary = await db.get(ReviewSummary, place_id)
    if summary is None:
        count = await db.scalar(
            select(func.count())
            .select_from(Review)
            .where(Review.place_id == place_id, Review.status == "published")
        )
        if count < MIN_REVIEWS:
            return ReviewSummaryRead(status="not_enough_reviews")
        if not settings.AI_ENABLED:
            return ReviewSummaryRead(status="disabled")
        _wake_worker()
        return ReviewSummaryRead(status="pending")

    stale = place_id in await stale_place_ids(db)
    if stale:
        _wake_worker()

    def points(raw: list) -> list[SummaryPoint]:
        return [SummaryPoint(**p) for p in raw]

    return ReviewSummaryRead(
        status="ready",
        pros=points(summary.pros),
        cons=points(summary.cons),
        best_for=points(summary.best_for),
        based_on_reviews=len(summary.review_ids),
        generated_at=summary.generated_at,
        model=summary.model,
        stale=stale,
    )


def _wake_worker() -> None:
    from app.ai import worker  # avoid an import cycle at module load

    worker.wake()
