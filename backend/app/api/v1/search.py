from fastapi import APIRouter, HTTPException, Query

from app.core.deps import DB, OptionalUserID
from app.schemas.place import Category, PriceTier
from app.schemas.search import HybridSearchResponse
from app.services import hybrid_search_service, search_service

router = APIRouter(prefix="/search", tags=["search"])


@router.get("")
async def search(
    db: DB,
    q: str = Query(..., min_length=2, max_length=100),
    type: str = Query("all", pattern="^(all|places|posts|users|hashtags)$"),
    limit: int = Query(20, ge=1, le=50),
):
    return await search_service.search(db, q, type, limit)


@router.get("/hybrid", response_model=HybridSearchResponse)
async def hybrid_search(
    db: DB,
    user_id: OptionalUserID,
    q: str = Query(..., min_length=2, max_length=200),
    category: Category | None = None,
    price_tier: PriceTier | None = None,
    area: str | None = Query(None, max_length=100),
    near_lat: float | None = Query(None, ge=-90, le=90),
    near_lng: float | None = Query(None, ge=-180, le=180),
    radius_m: int | None = Query(None, ge=100, le=100_000),
    limit: int = Query(10, ge=1, le=30),
):
    """Natural-language place search ("quiet rooftop cafe in Dhanmondi with
    good wifi"): semantic + keyword + distance, with hard filters."""
    if (near_lat is None) != (near_lng is None):
        raise HTTPException(422, detail="near_lat and near_lng go together")
    if radius_m is not None and near_lat is None:
        raise HTTPException(422, detail="radius_m needs near_lat and near_lng")
    return await hybrid_search_service.hybrid_search(
        db,
        q,
        category=category,
        price_tier=price_tier,
        area=area,
        near_lat=near_lat,
        near_lng=near_lng,
        radius_m=radius_m,
        limit=limit,
        user_id=user_id,
    )
