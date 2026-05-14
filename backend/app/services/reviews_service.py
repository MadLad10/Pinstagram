import uuid
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.place import Place
from app.models.review import Review
from app.models.user import User
from app.schemas.review import PaginatedReviews, ReviewCreate, ReviewRead, ReviewUpdate


async def create_review(db: AsyncSession, user_id: uuid.UUID, place_id: uuid.UUID, data: ReviewCreate) -> ReviewRead:
    from fastapi import HTTPException, status
    existing = await db.execute(select(Review).where(Review.user_id == user_id, Review.place_id == place_id))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You already reviewed this place")

    review = Review(user_id=user_id, place_id=place_id, rating=data.rating, body=data.body, price_paid=data.price_paid, status="pending")
    db.add(review)
    await db.commit()
    await db.refresh(review)
    return ReviewRead.model_validate(review)


async def update_review(db: AsyncSession, user_id: uuid.UUID, review_id: uuid.UUID, data: ReviewUpdate) -> ReviewRead:
    from fastapi import HTTPException, status
    result = await db.execute(select(Review).where(Review.id == review_id))
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")
    if review.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your review")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(review, field, value)
    review.status = "pending"
    await db.commit()
    await db.refresh(review)
    return ReviewRead.model_validate(review)


async def delete_review(db: AsyncSession, user_id: uuid.UUID, review_id: uuid.UUID) -> None:
    from fastapi import HTTPException, status
    result = await db.execute(select(Review).where(Review.id == review_id))
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")
    if review.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your review")
    place_id = review.place_id
    await db.delete(review)
    await db.commit()
    await _recompute_rating(db, place_id)


async def list_reviews(db: AsyncSession, place_id: uuid.UUID, cursor: str | None, limit: int) -> PaginatedReviews:
    import base64, json
    query = select(Review).where(Review.place_id == place_id, Review.status == "published")
    if cursor:
        try:
            cur = json.loads(base64.b64decode(cursor).decode())
            query = query.where(Review.id > cur["id"])
        except Exception:
            pass
    query = query.order_by(Review.created_at.desc()).limit(limit + 1)
    result = await db.execute(query)
    reviews = result.scalars().all()
    has_more = len(reviews) > limit
    reviews = reviews[:limit]

    items = []
    for r in reviews:
        user_r = await db.execute(select(User).where(User.id == r.user_id))
        u = user_r.scalar_one_or_none()
        read = ReviewRead.model_validate(r)
        if u:
            read.author_name = u.name
            read.author_avatar_url = u.avatar_url
        items.append(read)

    next_cursor = base64.b64encode(json.dumps({"id": str(reviews[-1].id)}).encode()).decode() if has_more and reviews else None
    return PaginatedReviews(items=items, next_cursor=next_cursor)


async def _recompute_rating(db: AsyncSession, place_id: uuid.UUID) -> None:
    result = await db.execute(
        select(func.avg(Review.rating), func.count(Review.id))
        .where(Review.place_id == place_id, Review.status == "published")
    )
    avg_rating, count = result.one()
    place_r = await db.execute(select(Place).where(Place.id == place_id))
    place = place_r.scalar_one_or_none()
    if place:
        place.avg_rating = round(float(avg_rating or 0), 1)
        place.review_count = count or 0
        await db.commit()
