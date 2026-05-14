import base64
import json
import uuid
from typing import Any

from geoalchemy2.functions import ST_AsGeoJSON, ST_DWithin, ST_GeogFromText, ST_MakePoint
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.place import Place
from app.models.social import SavedPlace
from app.schemas.place import PaginatedPlaces, PlaceCreate, PlaceRead, PlaceSummary, PlaceUpdate


def _encode_cursor(data: dict) -> str:
    return base64.b64encode(json.dumps(data).encode()).decode()


def _decode_cursor(cursor: str) -> dict:
    return json.loads(base64.b64decode(cursor).decode())


def _place_lat_lng(place: Any) -> tuple[float | None, float | None]:
    if place.location is None:
        return None, None
    geojson = json.loads(place._location_geojson) if hasattr(place, "_location_geojson") else None
    if geojson:
        coords = geojson["coordinates"]
        return coords[1], coords[0]
    return None, None


async def list_places(
    db: AsyncSession,
    category: str | None,
    division: str | None,
    district: str | None,
    area: str | None,
    price_tier: str | None,
    near_lat: float | None,
    near_lng: float | None,
    radius_m: int,
    min_rating: float | None,
    amenities: list[str] | None,
    q: str | None,
    cursor: str | None,
    limit: int,
    current_user_id: uuid.UUID | None = None,
) -> PaginatedPlaces:
    query = select(Place).where(Place.is_verified.is_(True))

    if category:
        query = query.where(Place.category == category)
    if division:
        query = query.where(Place.division == division)
    if district:
        query = query.where(Place.district == district)
    if area:
        query = query.where(Place.area == area)
    if price_tier:
        query = query.where(Place.price_tier == price_tier)
    if min_rating is not None:
        query = query.where(Place.avg_rating >= min_rating)
    if q:
        query = query.where(Place.name.ilike(f"%{q}%"))
    if near_lat is not None and near_lng is not None:
        point = func.ST_GeogFromText(f"POINT({near_lng} {near_lat})")
        query = query.where(func.ST_DWithin(Place.location, point, radius_m))

    if cursor:
        try:
            cur = _decode_cursor(cursor)
            query = query.where(Place.id > cur["id"])
        except Exception:
            pass

    query = query.order_by(Place.avg_rating.desc()).limit(limit + 1)
    result = await db.execute(query)
    places = result.scalars().all()

    has_more = len(places) > limit
    places = places[:limit]

    items = [PlaceSummary.model_validate(p) for p in places]
    next_cursor = _encode_cursor({"id": str(places[-1].id)}) if has_more else None
    return PaginatedPlaces(items=items, next_cursor=next_cursor)


async def get_place(
    db: AsyncSession,
    place_id: uuid.UUID,
    current_user_id: uuid.UUID | None = None,
) -> PlaceRead:
    result = await db.execute(select(Place).where(Place.id == place_id))
    place = result.scalar_one_or_none()
    if not place:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Place not found")

    is_saved = False
    if current_user_id:
        saved_result = await db.execute(
            select(SavedPlace).where(SavedPlace.user_id == current_user_id, SavedPlace.place_id == place_id)
        )
        is_saved = saved_result.scalar_one_or_none() is not None

    data = PlaceRead.model_validate(place)
    data.is_saved_by_me = is_saved
    return data


async def save_place(db: AsyncSession, user_id: uuid.UUID, place_id: uuid.UUID) -> None:
    from datetime import datetime, timezone
    result = await db.execute(
        select(SavedPlace).where(SavedPlace.user_id == user_id, SavedPlace.place_id == place_id)
    )
    if not result.scalar_one_or_none():
        sp = SavedPlace(user_id=user_id, place_id=place_id, created_at=datetime.now(timezone.utc).isoformat())
        db.add(sp)
        result2 = await db.execute(select(Place).where(Place.id == place_id))
        place = result2.scalar_one_or_none()
        if place:
            place.save_count = (place.save_count or 0) + 1
        await db.commit()


async def unsave_place(db: AsyncSession, user_id: uuid.UUID, place_id: uuid.UUID) -> None:
    result = await db.execute(
        select(SavedPlace).where(SavedPlace.user_id == user_id, SavedPlace.place_id == place_id)
    )
    sp = result.scalar_one_or_none()
    if sp:
        await db.delete(sp)
        result2 = await db.execute(select(Place).where(Place.id == place_id))
        place = result2.scalar_one_or_none()
        if place and place.save_count > 0:
            place.save_count -= 1
        await db.commit()


async def create_place(db: AsyncSession, data: PlaceCreate) -> PlaceRead:
    from geoalchemy2.elements import WKTElement
    location = None
    if data.lat is not None and data.lng is not None:
        location = WKTElement(f"POINT({data.lng} {data.lat})", srid=4326)

    place = Place(
        name=data.name,
        category=data.category,
        description=data.description,
        address=data.address,
        division=data.division,
        district=data.district,
        area=data.area,
        location=location,
        phone=data.phone,
        website=data.website,
        price_tier=data.price_tier,
        opening_hours=data.opening_hours,
        amenities=data.amenities,
        is_verified=False,
    )
    db.add(place)
    await db.commit()
    await db.refresh(place)
    return PlaceRead.model_validate(place)


async def update_place(db: AsyncSession, place_id: uuid.UUID, data: PlaceUpdate) -> PlaceRead:
    from fastapi import HTTPException, status
    result = await db.execute(select(Place).where(Place.id == place_id))
    place = result.scalar_one_or_none()
    if not place:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Place not found")

    for field, value in data.model_dump(exclude_none=True).items():
        if field in ("lat", "lng"):
            continue
        setattr(place, field, value)

    if data.lat is not None and data.lng is not None:
        from geoalchemy2.elements import WKTElement
        place.location = WKTElement(f"POINT({data.lng} {data.lat})", srid=4326)

    await db.commit()
    await db.refresh(place)
    return PlaceRead.model_validate(place)
