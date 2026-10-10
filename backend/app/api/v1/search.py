from fastapi import APIRouter, Query

from app.core.deps import DB
from app.services import search_service

router = APIRouter(prefix="/search", tags=["search"])


@router.get("")
async def search(
    db: DB,
    q: str = Query(..., min_length=2, max_length=100),
    type: str = Query("all", pattern="^(all|places|posts|users|hashtags)$"),
    limit: int = Query(20, ge=1, le=50),
):
    return await search_service.search(db, q, type, limit)
