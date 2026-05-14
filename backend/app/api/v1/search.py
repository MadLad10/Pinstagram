from fastapi import APIRouter, Query

from app.core.deps import DB
from app.services import search_service

router = APIRouter(prefix="/search", tags=["search"])


@router.get("")
async def search(
    db: DB,
    q: str = Query(..., min_length=2),
    type: str = Query("all", pattern="^(all|places|posts|users|hashtags)$"),
    cursor: str | None = None,
    limit: int = Query(20, le=50),
):
    return await search_service.search(db, q, type, cursor, limit)
