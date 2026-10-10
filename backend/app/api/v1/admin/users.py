import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, or_, select, tuple_

from app.api.v1.admin.schemas import PromoteBody, ReasonBody
from app.core.deps import DB, AdminUserID
from app.core.pagination import decode_cursor, encode_cursor
from app.models.post import Post
from app.models.social import Follow
from app.models.user import User
from app.services.admin_service import get_or_404, log_action
from app.services.auth_service import revoke_all_sessions

router = APIRouter()


@router.get("/users")
async def search_users(
    db: DB,
    _admin: AdminUserID,
    search: str = "",
    cursor: str | None = None,
    limit: int = Query(20, ge=1, le=50),
):
    post_count = (
        select(func.count())
        .where(Post.user_id == User.id)
        .correlate(User)
        .scalar_subquery()
    )
    follower_count = (
        select(func.count())
        .where(Follow.followee_id == User.id)
        .correlate(User)
        .scalar_subquery()
    )
    query = select(User, post_count, follower_count)
    if search:
        pattern = f"%{search}%"
        query = query.where(or_(User.email.ilike(pattern), User.name.ilike(pattern)))
    if cursor:
        c = decode_cursor(cursor, t=datetime, id=uuid.UUID)
        query = query.where(tuple_(User.created_at, User.id) < tuple_(c["t"], c["id"]))
    rows = (
        await db.execute(
            query.order_by(User.created_at.desc(), User.id.desc()).limit(limit + 1)
        )
    ).all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    return {
        "items": [
            {
                "id": str(u.id),
                "email": u.email,
                "name": u.name,
                "role": u.role,
                "is_banned": u.banned_at is not None,
                "is_deleted": u.deleted_at is not None,
                "created_at": u.created_at.isoformat(),
                "post_count": posts,
                "follower_count": followers,
            }
            for u, posts, followers in rows
        ],
        "next_cursor": encode_cursor(t=rows[-1][0].created_at, id=rows[-1][0].id)
        if has_more
        else None,
    }


@router.post("/users/{user_id}/ban", status_code=204)
async def ban_user(
    user_id: uuid.UUID, db: DB, admin: AdminUserID, body: ReasonBody | None = None
):
    if user_id == admin:
        raise HTTPException(status_code=400, detail="You cannot ban yourself")
    user = await get_or_404(db, User, user_id)
    user.banned_at = datetime.now(UTC)
    await revoke_all_sessions(db, user_id)
    log_action(
        db,
        admin,
        "ban_user",
        "user",
        user_id,
        {"reason": body.reason if body else None},
    )
    await db.commit()


@router.post("/users/{user_id}/unban", status_code=204)
async def unban_user(user_id: uuid.UUID, db: DB, admin: AdminUserID):
    user = await get_or_404(db, User, user_id)
    user.banned_at = None
    log_action(db, admin, "unban_user", "user", user_id)
    await db.commit()


@router.post("/users/{user_id}/promote", status_code=204)
async def promote_user(
    user_id: uuid.UUID, db: DB, admin: AdminUserID, body: PromoteBody | None = None
):
    role = body.role if body else "admin"
    user = await get_or_404(db, User, user_id)
    user.role = role
    # Roles live in the access token; force a re-login so the change applies.
    await revoke_all_sessions(db, user_id)
    log_action(db, admin, "set_role", "user", user_id, {"role": role})
    await db.commit()
