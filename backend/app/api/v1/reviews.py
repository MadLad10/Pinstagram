import uuid

from fastapi import APIRouter, Query

from app.core.deps import CurrentUserID, DB
from app.schemas.review import PaginatedReviews, ReviewCreate, ReviewRead, ReviewUpdate
from app.services import reviews_service

router = APIRouter(tags=["reviews"])


@router.post("/places/{place_id}/reviews", response_model=ReviewRead, status_code=201)
async def create_review(place_id: uuid.UUID, body: ReviewCreate, user_id: CurrentUserID, db: DB):
    return await reviews_service.create_review(db, user_id, place_id, body)


@router.get("/places/{place_id}/reviews", response_model=PaginatedReviews)
async def list_reviews(place_id: uuid.UUID, db: DB, cursor: str | None = None, limit: int = Query(20, le=50)):
    return await reviews_service.list_reviews(db, place_id, cursor, limit)


@router.patch("/reviews/{review_id}", response_model=ReviewRead)
async def update_review(review_id: uuid.UUID, body: ReviewUpdate, user_id: CurrentUserID, db: DB):
    return await reviews_service.update_review(db, user_id, review_id, body)


@router.delete("/reviews/{review_id}", status_code=204)
async def delete_review(review_id: uuid.UUID, user_id: CurrentUserID, db: DB):
    await reviews_service.delete_review(db, user_id, review_id)
