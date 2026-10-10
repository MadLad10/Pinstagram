import uuid
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import func, select, tuple_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import decode_cursor, encode_cursor
from app.models.place import Place
from app.models.review import Review
from app.models.user import User
from app.schemas.review import PaginatedReviews, ReviewCreate, ReviewRead, ReviewUpdate


def _review_read(review: Review, author: User | None = None) -> ReviewRead:
    read = ReviewRead.model_validate(review)
    if author:
        read.author_name = author.name
        read.author_avatar_url = author.avatar_url
    return read


async def recompute_place_rating(db: AsyncSession, place_id: uuid.UUID) -> None:
    """Refresh places.avg_rating / review_count from published reviews.
    Runs in the caller's transaction; the caller commits."""
    avg_rating, count = (
        await db.execute(
            select(func.avg(Review.rating), func.count(Review.id)).where(
                Review.place_id == place_id, Review.status == "published"
            )
        )
    ).one()
    await db.execute(
        update(Place)
        .where(Place.id == place_id)
        .values(avg_rating=round(float(avg_rating or 0), 1), review_count=count or 0)
    )


async def _own_review_or_error(
    db: AsyncSession, user_id: uuid.UUID, review_id: uuid.UUID
) -> Review:
    review = (
        await db.execute(select(Review).where(Review.id == review_id))
    ).scalar_one_or_none()
    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Review not found"
        )
    if review.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not your review"
        )
    return review


async def create_review(
    db: AsyncSession, user_id: uuid.UUID, place_id: uuid.UUID, data: ReviewCreate
) -> ReviewRead:
    place = (
        await db.execute(
            select(Place.id).where(Place.id == place_id, Place.is_verified.is_(True))
        )
    ).scalar_one_or_none()
    if not place:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Place not found"
        )

    existing = await db.execute(
        select(Review.id).where(Review.user_id == user_id, Review.place_id == place_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already reviewed this place",
        )

    review = Review(
        user_id=user_id, place_id=place_id, status="pending", **data.model_dump()
    )
    db.add(review)
    await db.commit()
    await db.refresh(review)
    return _review_read(review)


async def update_review(
    db: AsyncSession, user_id: uuid.UUID, review_id: uuid.UUID, data: ReviewUpdate
) -> ReviewRead:
    review = await _own_review_or_error(db, user_id, review_id)
    was_published = review.status == "published"
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(review, field, value)
    # Edits go back through moderation, so the old rating stops counting.
    review.status = "pending"
    await db.flush()
    if was_published:
        await recompute_place_rating(db, review.place_id)
    await db.commit()
    await db.refresh(review)
    return _review_read(review)


async def delete_review(
    db: AsyncSession, user_id: uuid.UUID, review_id: uuid.UUID
) -> None:
    review = await _own_review_or_error(db, user_id, review_id)
    place_id = review.place_id
    await db.delete(review)
    await db.flush()
    await recompute_place_rating(db, place_id)
    await db.commit()


async def list_reviews(
    db: AsyncSession, place_id: uuid.UUID, cursor: str | None, limit: int
) -> PaginatedReviews:
    query = (
        select(Review, User)
        .outerjoin(User, User.id == Review.user_id)
        .where(Review.place_id == place_id, Review.status == "published")
    )
    if cursor:
        c = decode_cursor(cursor, t=datetime, id=uuid.UUID)
        query = query.where(
            tuple_(Review.created_at, Review.id) < tuple_(c["t"], c["id"])
        )
    query = query.order_by(Review.created_at.desc(), Review.id.desc()).limit(limit + 1)

    rows = (await db.execute(query)).all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = (
        encode_cursor(t=rows[-1][0].created_at, id=rows[-1][0].id) if has_more else None
    )
    return PaginatedReviews(
        items=[_review_read(r, u) for r, u in rows], next_cursor=next_cursor
    )
