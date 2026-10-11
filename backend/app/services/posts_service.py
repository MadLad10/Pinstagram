import uuid
from datetime import UTC, datetime, timedelta

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import HTTPException, status
from sqlalchemy import delete, func, select, tuple_, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.core.pagination import decode_cursor, encode_cursor
from app.models.place import Place
from app.models.post import Post, PostComment, PostLike
from app.models.social import SavedPlace
from app.models.user import User
from app.schemas.post import (
    AuthorSnippet,
    CommentRead,
    PaginatedComments,
    PaginatedPosts,
    PlaceSnippet,
    PostCreate,
    PostRead,
)
from app.services import notifications_service
from app.services.uploads_service import MAX_SIZE, s3_client


def _build_post_read(
    post: Post, user: User, place: Place, liked: bool = False, saved: bool = False
) -> PostRead:
    return PostRead(
        id=post.id,
        media_url=post.media_url,
        media_type=post.media_type,
        thumbnail_url=post.thumbnail_url,
        caption=post.caption,
        hashtags=post.hashtags,
        price_mentioned=post.price_mentioned,
        rating=post.rating,
        status=post.status,
        like_count=post.like_count,
        comment_count=post.comment_count,
        is_liked_by_me=liked,
        is_saved_by_me=saved,
        author=AuthorSnippet.model_validate(user),
        place=PlaceSnippet(
            id=place.id,
            name=place.name,
            category=place.category,
            area=place.area,
            district=place.district,
            avg_rating=float(place.avg_rating),
        ),
        created_at=post.created_at,
    )


async def _visible_post_or_404(
    db: AsyncSession, post_id: uuid.UUID, viewer_id: uuid.UUID | None
) -> Post:
    """A post the viewer may see: published, or their own."""
    post = (
        await db.execute(select(Post).where(Post.id == post_id))
    ).scalar_one_or_none()
    if not post or (post.status != "published" and post.user_id != viewer_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found"
        )
    return post


async def _media_size(file_key: str) -> int:
    def _head() -> int:
        obj = s3_client().head_object(Bucket=settings.S3_BUCKET, Key=file_key)
        return obj["ContentLength"]

    try:
        return await run_in_threadpool(_head)
    except (ClientError, BotoCoreError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="File not found in storage"
        ) from None


async def create_post(
    db: AsyncSession, user_id: uuid.UUID, data: PostCreate
) -> PostRead:
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one()
    place = (
        await db.execute(
            select(Place).where(Place.id == data.place_id, Place.is_verified.is_(True))
        )
    ).scalar_one_or_none()
    if not place:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Place not found"
        )

    if not user.is_premium:
        since = datetime.now(UTC) - timedelta(days=1)
        posted_today = (
            await db.execute(
                select(func.count())
                .select_from(Post)
                .where(Post.user_id == user_id, Post.created_at > since)
            )
        ).scalar_one()
        if posted_today >= settings.FREE_POSTS_PER_DAY:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Free accounts can post {settings.FREE_POSTS_PER_DAY} times per day",
            )

    if await _media_size(data.file_key) > MAX_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="File too large (max 50 MB)"
        )

    post = Post(
        user_id=user_id,
        place_id=place.id,
        media_url=f"{settings.media_base_url}/{data.file_key}",
        media_type=data.media_type,
        caption=data.caption,
        hashtags=data.hashtags,
        price_mentioned=data.price_mentioned,
        rating=data.rating,
        status="pending",
    )
    db.add(post)
    await db.commit()
    await db.refresh(post)
    return _build_post_read(post, user, place)


async def get_post(
    db: AsyncSession, post_id: uuid.UUID, viewer_id: uuid.UUID | None = None
) -> PostRead:
    post = await _visible_post_or_404(db, post_id, viewer_id)
    user = (await db.execute(select(User).where(User.id == post.user_id))).scalar_one()
    place = (
        await db.execute(select(Place).where(Place.id == post.place_id))
    ).scalar_one()

    liked = saved = False
    if viewer_id:
        liked = (
            await db.execute(
                select(PostLike).where(
                    PostLike.user_id == viewer_id, PostLike.post_id == post_id
                )
            )
        ).scalar_one_or_none() is not None
        saved = (
            await db.execute(
                select(SavedPlace).where(
                    SavedPlace.user_id == viewer_id,
                    SavedPlace.place_id == post.place_id,
                )
            )
        ).scalar_one_or_none() is not None
    return _build_post_read(post, user, place, liked, saved)


async def list_user_posts(
    db: AsyncSession,
    author_id: uuid.UUID,
    viewer_id: uuid.UUID | None,
    cursor: str | None,
    limit: int,
) -> PaginatedPosts:
    """A user's posts, newest first. Authors also see their pending/rejected posts."""
    query = (
        select(Post, User, Place)
        .join(User, User.id == Post.user_id)
        .join(Place, Place.id == Post.place_id)
        .where(Post.user_id == author_id, User.deleted_at.is_(None))
    )
    if viewer_id != author_id:
        query = query.where(Post.status == "published")
    if cursor:
        c = decode_cursor(cursor, t=datetime, id=uuid.UUID)
        query = query.where(tuple_(Post.created_at, Post.id) < tuple_(c["t"], c["id"]))
    query = query.order_by(Post.created_at.desc(), Post.id.desc()).limit(limit + 1)

    rows = (await db.execute(query)).all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    items = [_build_post_read(p, u, pl) for p, u, pl in rows]
    next_cursor = (
        encode_cursor(t=rows[-1][0].created_at, id=rows[-1][0].id) if has_more else None
    )
    return PaginatedPosts(items=items, next_cursor=next_cursor)


async def delete_post(db: AsyncSession, post_id: uuid.UUID, user_id: uuid.UUID) -> None:
    post = (
        await db.execute(select(Post).where(Post.id == post_id))
    ).scalar_one_or_none()
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found"
        )
    if post.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not your post"
        )
    await db.delete(post)
    await db.commit()


async def like_post(db: AsyncSession, user_id: uuid.UUID, post_id: uuid.UUID) -> None:
    post = await _visible_post_or_404(db, post_id, user_id)
    inserted = (
        await db.execute(
            insert(PostLike)
            .values(user_id=user_id, post_id=post_id, created_at=datetime.now(UTC))
            .on_conflict_do_nothing()
            .returning(PostLike.post_id)
        )
    ).first()
    if inserted:
        await db.execute(
            update(Post)
            .where(Post.id == post_id)
            .values(like_count=Post.like_count + 1)
        )
        notifications_service.notify(
            db, user_id=post.user_id, actor_id=user_id, type="like", post_id=post_id
        )
    await db.commit()


async def unlike_post(db: AsyncSession, user_id: uuid.UUID, post_id: uuid.UUID) -> None:
    deleted = (
        await db.execute(
            delete(PostLike)
            .where(PostLike.user_id == user_id, PostLike.post_id == post_id)
            .returning(PostLike.post_id)
        )
    ).first()
    if deleted:
        await db.execute(
            update(Post)
            .where(Post.id == post_id, Post.like_count > 0)
            .values(like_count=Post.like_count - 1)
        )
    await db.commit()


def _comment_read(c: PostComment, author: User | None) -> CommentRead:
    return CommentRead(
        id=c.id,
        user_id=c.user_id,
        body=c.body,
        created_at=c.created_at,
        author=AuthorSnippet.model_validate(author) if author else None,
    )


async def list_comments(
    db: AsyncSession,
    post_id: uuid.UUID,
    viewer_id: uuid.UUID | None,
    cursor: str | None,
    limit: int,
) -> PaginatedComments:
    """Oldest first, so a thread reads top to bottom."""
    await _visible_post_or_404(db, post_id, viewer_id)
    query = (
        select(PostComment, User)
        .outerjoin(User, User.id == PostComment.user_id)
        .where(PostComment.post_id == post_id)
    )
    if cursor:
        c = decode_cursor(cursor, t=datetime, id=uuid.UUID)
        query = query.where(
            tuple_(PostComment.created_at, PostComment.id) > tuple_(c["t"], c["id"])
        )
    query = query.order_by(PostComment.created_at.asc(), PostComment.id.asc()).limit(
        limit + 1
    )
    rows = (await db.execute(query)).all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = (
        encode_cursor(t=rows[-1][0].created_at, id=rows[-1][0].id) if has_more else None
    )
    return PaginatedComments(
        items=[_comment_read(c, u) for c, u in rows], next_cursor=next_cursor
    )


async def add_comment(
    db: AsyncSession, user_id: uuid.UUID, post_id: uuid.UUID, body: str
) -> CommentRead:
    post = await _visible_post_or_404(db, post_id, user_id)
    comment = PostComment(
        post_id=post_id, user_id=user_id, body=body, created_at=datetime.now(UTC)
    )
    db.add(comment)
    await db.execute(
        update(Post)
        .where(Post.id == post_id)
        .values(comment_count=Post.comment_count + 1)
    )
    notifications_service.notify(
        db,
        user_id=post.user_id,
        actor_id=user_id,
        type="comment",
        post_id=post_id,
        message=body[:140],
    )
    await db.commit()
    author = (await db.execute(select(User).where(User.id == user_id))).scalar_one()
    return _comment_read(comment, author)


async def delete_comment(
    db: AsyncSession, user_id: uuid.UUID, post_id: uuid.UUID, comment_id: uuid.UUID
) -> None:
    comment = (
        await db.execute(
            select(PostComment).where(
                PostComment.id == comment_id, PostComment.post_id == post_id
            )
        )
    ).scalar_one_or_none()
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found"
        )

    post = (await db.execute(select(Post).where(Post.id == post_id))).scalar_one()
    # Comment authors and the post's author may delete a comment.
    if comment.user_id != user_id and post.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")

    await db.delete(comment)
    await db.execute(
        update(Post)
        .where(Post.id == post_id, Post.comment_count > 0)
        .values(comment_count=Post.comment_count - 1)
    )
    await db.commit()
