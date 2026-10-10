import uuid

from fastapi import APIRouter, Query

from app.core.deps import DB
from app.schemas.directions import DirectionsResponse
from app.services import directions_service

router = APIRouter(tags=["directions"])


@router.get("/places/{place_id}/directions", response_model=DirectionsResponse)
async def get_directions(
    place_id: uuid.UUID,
    db: DB,
    from_lat: float = Query(..., ge=-90, le=90),
    from_lng: float = Query(..., ge=-180, le=180),
):
    return await directions_service.get_directions(db, place_id, from_lat, from_lng)
