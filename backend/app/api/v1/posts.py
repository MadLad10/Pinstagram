import uuid

from fastapi import APIRouter, Depends, Query

from app.core.deps import DB, CurrentUserID, OptionalUserID
from app.core.rate_limit import rate_limit
from app.schemas.post import (
    CommentCreate,
    CommentRead,
    PaginatedComments,
    PostCreate,
    PostRead,
)
from app.services import posts_service

router = APIRouter(prefix="/posts", tags=["posts"])


@router.post("", response_model=PostRead, status_code=201)
async def create_post(body: PostCreate, user_id: CurrentUserID, db: DB):
    return await posts_service.create_post(db, user_id, body)


@router.get("/{post_id}", response_model=PostRead)
async def get_post(post_id: uuid.UUID, db: DB, user_id: OptionalUserID):
    return await posts_service.get_post(db, post_id, user_id)


@router.delete("/{post_id}", status_code=204)
async def delete_post(post_id: uuid.UUID, user_id: CurrentUserID, db: DB):
    await posts_service.delete_post(db, post_id, user_id)


@router.post("/{post_id}/like", status_code=204)
async def like_post(post_id: uuid.UUID, user_id: CurrentUserID, db: DB):
    await posts_service.like_post(db, user_id, post_id)


@router.delete("/{post_id}/like", status_code=204)
async def unlike_post(post_id: uuid.UUID, user_id: CurrentUserID, db: DB):
    await posts_service.unlike_post(db, user_id, post_id)


@router.get("/{post_id}/comments", response_model=PaginatedComments)
async def list_comments(
    post_id: uuid.UUID,
    db: DB,
    user_id: OptionalUserID,
    cursor: str | None = None,
    limit: int = Query(20, ge=1, le=50),
):
    return await posts_service.list_comments(db, post_id, user_id, cursor, limit)


@router.post(
    "/{post_id}/comments",
    response_model=CommentRead,
    status_code=201,
    dependencies=[Depends(rate_limit("comment", 30, 60, per="user"))],
)
async def add_comment(
    post_id: uuid.UUID, body: CommentCreate, user_id: CurrentUserID, db: DB
):
    return await posts_service.add_comment(db, user_id, post_id, body.body)


@router.delete("/{post_id}/comments/{comment_id}", status_code=204)
async def delete_comment(
    post_id: uuid.UUID, comment_id: uuid.UUID, user_id: CurrentUserID, db: DB
):
    await posts_service.delete_comment(db, user_id, post_id, comment_id)
