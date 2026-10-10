import uuid

from fastapi import APIRouter, Query

from app.core.deps import DB, CurrentUserID, OptionalUserID
from app.schemas.place import Category, PaginatedPlaces, PlaceRead, PriceTier
from app.services import places_service

router = APIRouter(prefix="/places", tags=["places"])


@router.get("", response_model=PaginatedPlaces)
async def list_places(
    db: DB,
    category: Category | None = None,
    division: str | None = None,
    district: str | None = None,
    area: str | None = None,
    price_tier: PriceTier | None = None,
    near_lat: float | None = Query(None, ge=-90, le=90),
    near_lng: float | None = Query(None, ge=-180, le=180),
    radius_m: int = Query(5000, ge=100, le=100_000),
    min_rating: float | None = Query(None, ge=0, le=5),
    amenities: str | None = Query(None, description="Comma-separated, all must match"),
    q: str | None = Query(None, max_length=100),
    cursor: str | None = None,
    limit: int = Query(20, ge=1, le=100),
):
    return await places_service.list_places(
        db,
        category=category,
        division=division,
        district=district,
        area=area,
        price_tier=price_tier,
        near_lat=near_lat,
        near_lng=near_lng,
        radius_m=radius_m,
        min_rating=min_rating,
        amenities=[a.strip() for a in amenities.split(",") if a.strip()]
        if amenities
        else None,
        q=q,
        cursor=cursor,
        limit=limit,
    )


@router.get("/{place_id}", response_model=PlaceRead)
async def get_place(place_id: uuid.UUID, db: DB, user_id: OptionalUserID):
    return await places_service.get_place(db, place_id, user_id)


@router.post("/{place_id}/save", status_code=204)
async def save_place(place_id: uuid.UUID, user_id: CurrentUserID, db: DB):
    await places_service.save_place(db, user_id, place_id)


@router.delete("/{place_id}/save", status_code=204)
async def unsave_place(place_id: uuid.UUID, user_id: CurrentUserID, db: DB):
    await places_service.unsave_place(db, user_id, place_id)
