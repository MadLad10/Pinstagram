from fastapi import APIRouter, Query

from app.core.deps import CurrentUserID, DB
from app.schemas.post import PaginatedPosts
from app.services import feed_service

router = APIRouter(prefix="/feed", tags=["feed"])


@router.get("", response_model=PaginatedPosts)
async def get_feed(
    user_id: CurrentUserID,
    db: DB,
    cursor: str | None = None,
    limit: int = Query(20, le=50),
    lat: float | None = None,
    lng: float | None = None,
):
    return await feed_service.get_feed(db, user_id, cursor, limit, lat, lng)


@router.get("/trending", response_model=PaginatedPosts)
async def get_trending(db: DB, cursor: str | None = None, limit: int = Query(20, le=50)):
    return await feed_service.get_trending(db, cursor, limit)


@router.get("/nearby", response_model=PaginatedPosts)
async def get_nearby(
    db: DB,
    lat: float = Query(...),
    lng: float = Query(...),
    radius_m: int = 50000,
    cursor: str | None = None,
    limit: int = Query(20, le=50),
    user_id: CurrentUserID = None,
):
    return await feed_service.get_feed(db, user_id, cursor, limit, lat, lng)
