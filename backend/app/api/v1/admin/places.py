import uuid
from fastapi import APIRouter, Query
from app.core.deps import AdminUserID, DB
from app.models.place import Place
from app.schemas.place import PlaceCreate, PlaceRead, PlaceUpdate
from app.services import places_service
from sqlalchemy import select

router = APIRouter()


@router.get("/places/pending")
async def list_pending_places(db: DB, _admin: AdminUserID, cursor: str | None = None, limit: int = Query(20, le=50)):
    import base64, json
    result = await db.execute(select(Place).where(Place.is_verified == False).order_by(Place.created_at.asc()).limit(limit + 1))
    places = result.scalars().all()
    has_more = len(places) > limit
    places = places[:limit]
    items = [{"id": str(p.id), "name": p.name, "category": p.category, "address": p.address,
              "created_at": p.created_at.isoformat()} for p in places]
    next_cursor = base64.b64encode(json.dumps({"id": str(places[-1].id)}).encode()).decode() if has_more and places else None
    return {"items": items, "next_cursor": next_cursor}


@router.post("/places", response_model=PlaceRead, status_code=201)
async def create_place(body: PlaceCreate, db: DB, _admin: AdminUserID):
    place = await places_service.create_place(db, body)
    result = await db.execute(select(Place).where(Place.id == place.id))
    p = result.scalar_one()
    p.is_verified = True
    await db.commit()
    return place


@router.patch("/places/{place_id}", response_model=PlaceRead)
async def update_place(place_id: uuid.UUID, body: PlaceUpdate, db: DB, _admin: AdminUserID):
    return await places_service.update_place(db, place_id, body)


@router.post("/places/{place_id}/approve", status_code=204)
async def approve_place(place_id: uuid.UUID, db: DB, _admin: AdminUserID):
    from app.services.admin_service import log_action
    result = await db.execute(select(Place).where(Place.id == place_id))
    place = result.scalar_one_or_none()
    if place:
        place.is_verified = True
        await db.commit()
        await log_action(db, _admin, "approve_place", "place", place_id)
