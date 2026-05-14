import uuid
from fastapi import APIRouter, Query
from app.core.deps import AdminUserID, DB
from app.models.review import Review
from sqlalchemy import select

router = APIRouter()


@router.get("/reviews/pending")
async def list_pending_reviews(db: DB, _admin: AdminUserID, cursor: str | None = None, limit: int = Query(20, le=50)):
    import base64, json
    result = await db.execute(select(Review).where(Review.status == "pending").order_by(Review.created_at.asc()).limit(limit + 1))
    reviews = result.scalars().all()
    has_more = len(reviews) > limit
    reviews = reviews[:limit]
    items = [{"id": str(r.id), "user_id": str(r.user_id), "place_id": str(r.place_id),
              "rating": r.rating, "body": r.body, "created_at": r.created_at.isoformat()} for r in reviews]
    next_cursor = base64.b64encode(json.dumps({"id": str(reviews[-1].id)}).encode()).decode() if has_more and reviews else None
    return {"items": items, "next_cursor": next_cursor}


@router.post("/reviews/{review_id}/approve", status_code=204)
async def approve_review(review_id: uuid.UUID, db: DB, _admin: AdminUserID):
    from app.services.admin_service import log_action
    from app.services.reviews_service import _recompute_rating
    result = await db.execute(select(Review).where(Review.id == review_id))
    review = result.scalar_one_or_none()
    if review:
        review.status = "published"
        await db.commit()
        await _recompute_rating(db, review.place_id)
        await log_action(db, _admin, "approve_review", "review", review_id)


@router.post("/reviews/{review_id}/reject", status_code=204)
async def reject_review(review_id: uuid.UUID, db: DB, _admin: AdminUserID, body: dict):
    from app.services.admin_service import log_action
    result = await db.execute(select(Review).where(Review.id == review_id))
    review = result.scalar_one_or_none()
    if review:
        review.status = "rejected"
        await db.commit()
        await log_action(db, _admin, "reject_review", "review", review_id, body)
