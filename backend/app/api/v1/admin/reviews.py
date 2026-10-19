import uuid
from datetime import datetime

from fastapi import APIRouter, Query
from sqlalchemy import select, tuple_

from app.ai import worker
from app.api.v1.admin.schemas import ReasonBody
from app.core.deps import DB, AdminUserID
from app.core.pagination import decode_cursor, encode_cursor
from app.models.place import Place
from app.models.review import Review
from app.models.user import User
from app.services.admin_service import get_or_404, log_action
from app.services.notifications_service import notify
from app.services.reviews_service import recompute_place_rating

router = APIRouter()


@router.get("/reviews/pending")
async def list_pending_reviews(
    db: DB,
    _admin: AdminUserID,
    cursor: str | None = None,
    limit: int = Query(20, ge=1, le=50),
):
    query = (
        select(Review, User.name, Place.name)
        .join(User, User.id == Review.user_id)
        .join(Place, Place.id == Review.place_id)
        .where(Review.status == "pending")
    )
    if cursor:
        c = decode_cursor(cursor, t=datetime, id=uuid.UUID)
        query = query.where(
            tuple_(Review.created_at, Review.id) > tuple_(c["t"], c["id"])
        )
    rows = (
        await db.execute(query.order_by(Review.created_at, Review.id).limit(limit + 1))
    ).all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    return {
        "items": [
            {
                "id": str(r.id),
                "user_id": str(r.user_id),
                "author_name": author,
                "place_id": str(r.place_id),
                "place_name": place,
                "rating": r.rating,
                "body": r.body,
                "price_paid": r.price_paid,
                "created_at": r.created_at.isoformat(),
            }
            for r, author, place in rows
        ],
        "next_cursor": encode_cursor(t=rows[-1][0].created_at, id=rows[-1][0].id)
        if has_more
        else None,
    }


@router.post("/reviews/{review_id}/approve", status_code=204)
async def approve_review(review_id: uuid.UUID, db: DB, admin: AdminUserID):
    review = await get_or_404(db, Review, review_id)
    review.status = "published"
    await db.flush()
    await recompute_place_rating(db, review.place_id)
    notify(db, user_id=review.user_id, type="review_approved", place_id=review.place_id)
    log_action(db, admin, "approve_review", "review", review_id)
    await db.commit()
    worker.wake()  # make the review searchable now, not at the next poll


@router.post("/reviews/{review_id}/reject", status_code=204)
async def reject_review(
    review_id: uuid.UUID, db: DB, admin: AdminUserID, body: ReasonBody
):
    review = await get_or_404(db, Review, review_id)
    was_published = review.status == "published"
    review.status = "rejected"
    await db.flush()
    if was_published:
        await recompute_place_rating(db, review.place_id)
    log_action(db, admin, "reject_review", "review", review_id, {"reason": body.reason})
    await db.commit()
    worker.wake()
