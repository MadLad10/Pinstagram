from fastapi import APIRouter, Query

from app.core.deps import DB, CurrentUserID
from app.schemas.notification import PaginatedNotifications
from app.services import notifications_service

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=PaginatedNotifications)
async def list_notifications(
    user_id: CurrentUserID,
    db: DB,
    cursor: str | None = None,
    limit: int = Query(20, ge=1, le=50),
):
    return await notifications_service.list_notifications(db, user_id, cursor, limit)


@router.post("/read-all", status_code=204)
async def mark_all_read(user_id: CurrentUserID, db: DB):
    await notifications_service.mark_all_read(db, user_id)
