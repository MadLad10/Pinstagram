import uuid
from fastapi import APIRouter, Query
from app.core.deps import AdminUserID, DB
from app.models.post import Post
from app.schemas.post import PaginatedPosts
from sqlalchemy import select

router = APIRouter()


@router.get("/posts/pending")
async def list_pending_posts(db: DB, _admin: AdminUserID, cursor: str | None = None, limit: int = Query(20, le=50)):
    import base64, json
    query = select(Post).where(Post.status == "pending").order_by(Post.created_at.asc()).limit(limit + 1)
    result = await db.execute(query)
    posts = result.scalars().all()
    has_more = len(posts) > limit
    posts = posts[:limit]
    items = [{"id": str(p.id), "user_id": str(p.user_id), "place_id": str(p.place_id),
              "media_url": p.media_url, "media_type": p.media_type, "caption": p.caption,
              "created_at": p.created_at.isoformat()} for p in posts]
    next_cursor = base64.b64encode(json.dumps({"id": str(posts[-1].id)}).encode()).decode() if has_more and posts else None
    return {"items": items, "next_cursor": next_cursor}


@router.post("/posts/{post_id}/approve", status_code=204)
async def approve_post(post_id: uuid.UUID, db: DB, _admin: AdminUserID):
    from app.services.admin_service import log_action
    result = await db.execute(select(Post).where(Post.id == post_id))
    post = result.scalar_one_or_none()
    if post:
        post.status = "published"
        await db.commit()
        await log_action(db, _admin, "approve_post", "post", post_id)


@router.post("/posts/{post_id}/reject", status_code=204)
async def reject_post(post_id: uuid.UUID, db: DB, _admin: AdminUserID, body: dict):
    from app.services.admin_service import log_action
    result = await db.execute(select(Post).where(Post.id == post_id))
    post = result.scalar_one_or_none()
    if post:
        post.status = "rejected"
        post.rejection_reason = body.get("reason", "")
        await db.commit()
        await log_action(db, _admin, "reject_post", "post", post_id, {"reason": body.get("reason")})
