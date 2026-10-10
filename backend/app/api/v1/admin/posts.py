import uuid
from datetime import datetime

from fastapi import APIRouter, Query
from sqlalchemy import select, tuple_

from app.api.v1.admin.schemas import ReasonBody
from app.core.deps import DB, AdminUserID
from app.core.pagination import decode_cursor, encode_cursor
from app.models.place import Place
from app.models.post import Post
from app.models.user import User
from app.services.admin_service import get_or_404, log_action
from app.services.notifications_service import notify

router = APIRouter()


@router.get("/posts/pending")
async def list_pending_posts(
    db: DB,
    _admin: AdminUserID,
    cursor: str | None = None,
    limit: int = Query(20, ge=1, le=50),
):
    """Moderation queue, oldest first."""
    query = (
        select(Post, User.name, Place.name)
        .join(User, User.id == Post.user_id)
        .join(Place, Place.id == Post.place_id)
        .where(Post.status == "pending")
    )
    if cursor:
        c = decode_cursor(cursor, t=datetime, id=uuid.UUID)
        query = query.where(tuple_(Post.created_at, Post.id) > tuple_(c["t"], c["id"]))
    rows = (
        await db.execute(query.order_by(Post.created_at, Post.id).limit(limit + 1))
    ).all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    return {
        "items": [
            {
                "id": str(p.id),
                "user_id": str(p.user_id),
                "author_name": author,
                "place_id": str(p.place_id),
                "place_name": place,
                "media_url": p.media_url,
                "media_type": p.media_type,
                "caption": p.caption,
                "created_at": p.created_at.isoformat(),
            }
            for p, author, place in rows
        ],
        "next_cursor": encode_cursor(t=rows[-1][0].created_at, id=rows[-1][0].id)
        if has_more
        else None,
    }


@router.post("/posts/{post_id}/approve", status_code=204)
async def approve_post(post_id: uuid.UUID, db: DB, admin: AdminUserID):
    post = await get_or_404(db, Post, post_id)
    post.status = "published"
    post.rejection_reason = None
    notify(db, user_id=post.user_id, type="post_approved", post_id=post.id)
    log_action(db, admin, "approve_post", "post", post_id)
    await db.commit()


@router.post("/posts/{post_id}/reject", status_code=204)
async def reject_post(post_id: uuid.UUID, db: DB, admin: AdminUserID, body: ReasonBody):
    post = await get_or_404(db, Post, post_id)
    post.status = "rejected"
    post.rejection_reason = body.reason
    notify(
        db,
        user_id=post.user_id,
        type="post_rejected",
        post_id=post.id,
        message=body.reason,
    )
    log_action(db, admin, "reject_post", "post", post_id, {"reason": body.reason})
    await db.commit()
