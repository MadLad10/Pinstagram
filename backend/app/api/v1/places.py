import uuid

from fastapi import APIRouter, Query

from app.core.deps import CurrentUserID, DB
from app.schemas.place import PaginatedPlaces, PlaceRead
from app.services import places_service

router = APIRouter(prefix="/places", tags=["places"])


@router.get("", response_model=PaginatedPlaces)
async def list_places(
    db: DB,
    category: str | None = None,
    division: str | None = None,
    district: str | None = None,
    area: str | None = None,
    price_tier: str | None = None,
    near_lat: float | None = None,
    near_lng: float | None = None,
    radius_m: int = 5000,
    min_rating: float | None = None,
    amenities: str | None = None,
    q: str | None = None,
    cursor: str | None = None,
    limit: int = Query(20, le=50),
):
    amenity_list = amenities.split(",") if amenities else None
    return await places_service.list_places(
        db, category, division, district, area, price_tier,
        near_lat, near_lng, radius_m, min_rating, amenity_list, q, cursor, limit,
    )


@router.get("/{place_id}", response_model=PlaceRead)
async def get_place(place_id: uuid.UUID, db: DB):
    return await places_service.get_place(db, place_id)


@router.post("/{place_id}/save", status_code=204)
async def save_place(place_id: uuid.UUID, user_id: CurrentUserID, db: DB):
    await places_service.save_place(db, user_id, place_id)


@router.delete("/{place_id}/save", status_code=204)
async def unsave_place(place_id: uuid.UUID, user_id: CurrentUserID, db: DB):
    await places_service.unsave_place(db, user_id, place_id)
