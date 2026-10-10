from fastapi import APIRouter, Query

from app.core.deps import DB, CurrentUserID, OptionalUserID
from app.schemas.post import PaginatedPosts
from app.services import feed_service

router = APIRouter(prefix="/feed", tags=["feed"])

Limit = Query(20, ge=1, le=50)


@router.get("", response_model=PaginatedPosts)
async def get_feed(
    user_id: CurrentUserID,
    db: DB,
    cursor: str | None = None,
    limit: int = Limit,
    lat: float | None = Query(None, ge=-90, le=90),
    lng: float | None = Query(None, ge=-180, le=180),
):
    return await feed_service.get_feed(db, user_id, cursor, limit, lat, lng)


@router.get("/trending", response_model=PaginatedPosts)
async def get_trending(
    db: DB, user_id: OptionalUserID, cursor: str | None = None, limit: int = Limit
):
    return await feed_service.get_trending(db, cursor, limit, user_id)


@router.get("/nearby", response_model=PaginatedPosts)
async def get_nearby(
    user_id: CurrentUserID,
    db: DB,
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
    radius_m: int = Query(50000, ge=100, le=200_000),
    cursor: str | None = None,
    limit: int = Limit,
):
    return await feed_service.get_nearby(db, user_id, lat, lng, radius_m, cursor, limit)
