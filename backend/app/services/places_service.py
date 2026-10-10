import re
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from geoalchemy2.elements import WKTElement
from sqlalchemy import delete, func, literal_column, select, tuple_, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import decode_cursor, encode_cursor
from app.models.place import Place
from app.models.social import SavedPlace
from app.schemas.place import (
    PaginatedPlaces,
    PlaceCreate,
    PlaceRead,
    PlaceSummary,
    PlaceUpdate,
)


def _point(lat: float, lng: float):
    return func.ST_SetSRID(func.ST_MakePoint(lng, lat), 4326).cast(Place.location.type)


def prefix_tsquery(q: str) -> str | None:
    """Turn free text into a safe prefix tsquery: "cafe ban" -> "cafe:* & ban:*".

    Only word characters survive, so user input can never inject tsquery syntax.
    """
    tokens = re.findall(r"\w+", q.lower())
    if not tokens:
        return None
    return " & ".join(f"{t}:*" for t in tokens[:8])


async def list_places(
    db: AsyncSession,
    *,
    category: str | None = None,
    division: str | None = None,
    district: str | None = None,
    area: str | None = None,
    price_tier: str | None = None,
    near_lat: float | None = None,
    near_lng: float | None = None,
    radius_m: int = 5000,
    min_rating: float | None = None,
    amenities: list[str] | None = None,
    q: str | None = None,
    cursor: str | None = None,
    limit: int = 20,
) -> PaginatedPlaces:
    """Verified places, best rated first, keyset-paginated on (avg_rating, id)."""
    distance = None
    columns = [Place]
    if near_lat is not None and near_lng is not None:
        distance = func.ST_Distance(Place.location, _point(near_lat, near_lng))
        columns.append(distance.label("distance_m"))

    query = select(*columns).where(Place.is_verified.is_(True))
    if category:
        query = query.where(Place.category == category)
    if division:
        query = query.where(Place.division == division)
    if district:
        query = query.where(Place.district == district)
    if area:
        query = query.where(Place.area.ilike(area))
    if price_tier:
        query = query.where(Place.price_tier == price_tier)
    if min_rating is not None:
        query = query.where(Place.avg_rating >= min_rating)
    if amenities:
        query = query.where(Place.amenities.contains(amenities))
    if q:
        tsq = prefix_tsquery(q)
        if tsq:
            query = query.where(
                literal_column("places.search_vector").op("@@")(
                    func.to_tsquery("simple", tsq)
                )
            )
    if distance is not None:
        query = query.where(
            func.ST_DWithin(Place.location, _point(near_lat, near_lng), radius_m)
        )

    if cursor:
        c = decode_cursor(cursor, r=float, id=uuid.UUID)
        query = query.where(
            tuple_(Place.avg_rating, Place.id) < tuple_(c["r"], c["id"])
        )

    query = query.order_by(Place.avg_rating.desc(), Place.id.desc()).limit(limit + 1)
    rows = (await db.execute(query)).all()
    has_more = len(rows) > limit
    rows = rows[:limit]

    items = []
    for row in rows:
        summary = PlaceSummary.model_validate(row[0])
        if distance is not None:
            summary.distance_m = round(row[1])
        items.append(summary)

    next_cursor = None
    if has_more:
        last = rows[-1][0]
        next_cursor = encode_cursor(r=float(last.avg_rating), id=last.id)
    return PaginatedPlaces(items=items, next_cursor=next_cursor)


async def _get_or_404(db: AsyncSession, place_id: uuid.UUID) -> Place:
    place = (
        await db.execute(select(Place).where(Place.id == place_id))
    ).scalar_one_or_none()
    if not place:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Place not found"
        )
    return place


async def get_place(
    db: AsyncSession, place_id: uuid.UUID, current_user_id: uuid.UUID | None = None
) -> PlaceRead:
    place = await _get_or_404(db, place_id)
    data = PlaceRead.model_validate(place)
    if current_user_id:
        saved = await db.execute(
            select(SavedPlace).where(
                SavedPlace.user_id == current_user_id, SavedPlace.place_id == place_id
            )
        )
        data.is_saved_by_me = saved.scalar_one_or_none() is not None
    return data


async def save_place(db: AsyncSession, user_id: uuid.UUID, place_id: uuid.UUID) -> None:
    await _get_or_404(db, place_id)
    # ON CONFLICT makes double-taps idempotent; the counter only moves when a
    # row was actually inserted.
    result = await db.execute(
        insert(SavedPlace)
        .values(user_id=user_id, place_id=place_id, created_at=datetime.now(UTC))
        .on_conflict_do_nothing()
        .returning(SavedPlace.place_id)
    )
    if result.first():
        await db.execute(
            update(Place)
            .where(Place.id == place_id)
            .values(save_count=Place.save_count + 1)
        )
    await db.commit()


async def unsave_place(
    db: AsyncSession, user_id: uuid.UUID, place_id: uuid.UUID
) -> None:
    result = await db.execute(
        delete(SavedPlace)
        .where(SavedPlace.user_id == user_id, SavedPlace.place_id == place_id)
        .returning(SavedPlace.place_id)
    )
    if result.first():
        await db.execute(
            update(Place)
            .where(Place.id == place_id, Place.save_count > 0)
            .values(save_count=Place.save_count - 1)
        )
    await db.commit()


async def create_place(
    db: AsyncSession, data: PlaceCreate, *, verified: bool = False
) -> PlaceRead:
    values = data.model_dump(exclude={"lat", "lng"})
    place = Place(**values, is_verified=verified)
    if data.lat is not None and data.lng is not None:
        place.location = WKTElement(f"POINT({data.lng} {data.lat})", srid=4326)
    db.add(place)
    await db.commit()
    await db.refresh(place)
    return PlaceRead.model_validate(place)


async def update_place(
    db: AsyncSession, place_id: uuid.UUID, data: PlaceUpdate
) -> PlaceRead:
    place = await _get_or_404(db, place_id)
    for field, value in data.model_dump(
        exclude_none=True, exclude={"lat", "lng"}
    ).items():
        setattr(place, field, value)
    if data.lat is not None and data.lng is not None:
        place.location = WKTElement(f"POINT({data.lng} {data.lat})", srid=4326)
    await db.commit()
    await db.refresh(place)
    return PlaceRead.model_validate(place)
