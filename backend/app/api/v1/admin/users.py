import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Query
from sqlalchemy import select
from app.core.deps import AdminUserID, DB
from app.models.user import User

router = APIRouter()


@router.get("/users")
async def search_users(db: DB, _admin: AdminUserID, q: str = "", limit: int = Query(20, le=50)):
    result = await db.execute(select(User).where(User.email.ilike(f"%{q}%") | User.name.ilike(f"%{q}%")).limit(limit))
    users = result.scalars().all()
    return [{"id": str(u.id), "email": u.email, "name": u.name, "role": u.role,
             "banned_at": u.banned_at, "deleted_at": u.deleted_at} for u in users]


@router.post("/users/{user_id}/ban", status_code=204)
async def ban_user(user_id: uuid.UUID, db: DB, _admin: AdminUserID):
    from app.services.admin_service import log_action
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user:
        user.banned_at = datetime.now(timezone.utc)
        await db.commit()
        await log_action(db, _admin, "ban_user", "user", user_id)


@router.post("/users/{user_id}/unban", status_code=204)
async def unban_user(user_id: uuid.UUID, db: DB, _admin: AdminUserID):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user:
        user.banned_at = None
        await db.commit()


@router.post("/users/{user_id}/promote", status_code=204)
async def promote_user(user_id: uuid.UUID, db: DB, _admin: AdminUserID, body: dict):
    from app.services.admin_service import log_action
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user:
        user.role = body.get("role", user.role)
        await db.commit()
        await log_action(db, _admin, "promote_user", "user", user_id, body)
