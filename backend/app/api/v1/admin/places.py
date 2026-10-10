import uuid
from datetime import datetime

from fastapi import APIRouter, Query
from sqlalchemy import select, tuple_

from app.core.deps import DB, AdminUserID
from app.core.pagination import decode_cursor, encode_cursor
from app.models.place import Place
from app.schemas.place import PlaceCreate, PlaceRead, PlaceUpdate
from app.services import places_service
from app.services.admin_service import get_or_404, log_action

router = APIRouter()


def _admin_place(p: Place) -> dict:
    return {
        "id": str(p.id),
        "name": p.name,
        "category": p.category,
        "address": p.address,
        "area": p.area,
        "lat": p.lat,
        "lng": p.lng,
        "avg_rating": float(p.avg_rating or 0),
        "review_count": p.review_count,
        "is_verified": p.is_verified,
        "is_featured": p.is_featured,
        "created_at": p.created_at.isoformat(),
    }


async def _page(db: DB, query, cursor: str | None, limit: int) -> dict:
    if cursor:
        c = decode_cursor(cursor, t=datetime, id=uuid.UUID)
        query = query.where(
            tuple_(Place.created_at, Place.id) < tuple_(c["t"], c["id"])
        )
    places = (
        (
            await db.execute(
                query.order_by(Place.created_at.desc(), Place.id.desc()).limit(
                    limit + 1
                )
            )
        )
        .scalars()
        .all()
    )
    has_more = len(places) > limit
    places = places[:limit]
    return {
        "items": [_admin_place(p) for p in places],
        "next_cursor": encode_cursor(t=places[-1].created_at, id=places[-1].id)
        if has_more
        else None,
    }


@router.get("/places")
async def list_all_places(
    db: DB,
    _admin: AdminUserID,
    q: str | None = None,
    cursor: str | None = None,
    limit: int = Query(20, ge=1, le=50),
):
    query = select(Place)
    if q:
        query = query.where(Place.name.ilike(f"%{q}%"))
    return await _page(db, query, cursor, limit)


@router.get("/places/pending")
async def list_pending_places(
    db: DB,
    _admin: AdminUserID,
    cursor: str | None = None,
    limit: int = Query(20, ge=1, le=50),
):
    return await _page(
        db, select(Place).where(Place.is_verified.is_(False)), cursor, limit
    )


@router.post("/places", response_model=PlaceRead, status_code=201)
async def create_place(body: PlaceCreate, db: DB, admin: AdminUserID):
    place = await places_service.create_place(db, body, verified=True)
    log_action(db, admin, "create_place", "place", place.id)
    await db.commit()
    return place


@router.patch("/places/{place_id}", response_model=PlaceRead)
async def update_place(
    place_id: uuid.UUID, body: PlaceUpdate, db: DB, admin: AdminUserID
):
    log_action(
        db, admin, "update_place", "place", place_id, body.model_dump(exclude_none=True)
    )
    return await places_service.update_place(db, place_id, body)


async def _set_flag(
    db: DB, admin: uuid.UUID, place_id: uuid.UUID, field: str, value: bool
):
    place = await get_or_404(db, Place, place_id)
    setattr(place, field, value)
    log_action(db, admin, f"{field}={value}", "place", place_id)
    await db.commit()


@router.post("/places/{place_id}/approve", status_code=204)
async def approve_place(place_id: uuid.UUID, db: DB, admin: AdminUserID):
    await _set_flag(db, admin, place_id, "is_verified", True)


@router.post("/places/{place_id}/feature", status_code=204)
async def feature_place(place_id: uuid.UUID, db: DB, admin: AdminUserID):
    await _set_flag(db, admin, place_id, "is_featured", True)


@router.post("/places/{place_id}/unfeature", status_code=204)
async def unfeature_place(place_id: uuid.UUID, db: DB, admin: AdminUserID):
    await _set_flag(db, admin, place_id, "is_featured", False)
