import base64
import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.post import Post, PostComment, PostLike
from app.models.user import User
from app.models.place import Place
from app.schemas.post import CommentRead, PaginatedComments, PaginatedPosts, PostCreate, PostRead


def _encode_cursor(data: dict) -> str:
    return base64.b64encode(json.dumps(data).encode()).decode()


def _decode_cursor(cursor: str) -> dict:
    return json.loads(base64.b64decode(cursor).decode())


def _build_post_read(post: Post, user: User, place: Place, liked: bool, saved: bool) -> PostRead:
    from app.schemas.post import AuthorSnippet, PlaceSnippet
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
        author=AuthorSnippet(id=user.id, name=user.name, avatar_url=user.avatar_url, is_verified=user.is_verified),
        place=PlaceSnippet(
            id=place.id, name=place.name, category=place.category,
            area=place.area, district=place.district, avg_rating=float(place.avg_rating),
        ),
        created_at=post.created_at,
    )


async def create_post(db: AsyncSession, user_id: uuid.UUID, data: PostCreate) -> PostRead:
    from app.core.config import settings
    import boto3

    s3 = boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        region_name=settings.S3_REGION,
    )
    try:
        s3.head_object(Bucket=settings.S3_BUCKET, Key=data.file_key)
    except Exception:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File not found in storage")

    media_url = f"{settings.S3_ENDPOINT}/{settings.S3_BUCKET}/{data.file_key}"

    post = Post(
        user_id=user_id,
        place_id=data.place_id,
        media_url=media_url,
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

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one()
    result = await db.execute(select(Place).where(Place.id == data.place_id))
    place = result.scalar_one()

    return _build_post_read(post, user, place, False, False)


async def get_post(db: AsyncSession, post_id: uuid.UUID, current_user_id: uuid.UUID | None = None) -> PostRead:
    from fastapi import HTTPException, status
    result = await db.execute(select(Post).where(Post.id == post_id))
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    if post.status != "published" and post.user_id != current_user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    result = await db.execute(select(User).where(User.id == post.user_id))
    user = result.scalar_one()
    result = await db.execute(select(Place).where(Place.id == post.place_id))
    place = result.scalar_one()

    liked = False
    saved = False
    if current_user_id:
        from app.models.social import SavedPlace
        liked_r = await db.execute(select(PostLike).where(PostLike.user_id == current_user_id, PostLike.post_id == post_id))
        liked = liked_r.scalar_one_or_none() is not None
        saved_r = await db.execute(select(SavedPlace).where(SavedPlace.user_id == current_user_id, SavedPlace.place_id == post.place_id))
        saved = saved_r.scalar_one_or_none() is not None

    return _build_post_read(post, user, place, liked, saved)


async def delete_post(db: AsyncSession, post_id: uuid.UUID, user_id: uuid.UUID) -> None:
    from fastapi import HTTPException, status
    result = await db.execute(select(Post).where(Post.id == post_id))
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    if post.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your post")
    await db.delete(post)
    await db.commit()


async def like_post(db: AsyncSession, user_id: uuid.UUID, post_id: uuid.UUID) -> None:
    result = await db.execute(select(PostLike).where(PostLike.user_id == user_id, PostLike.post_id == post_id))
    if not result.scalar_one_or_none():
        like = PostLike(user_id=user_id, post_id=post_id, created_at=datetime.now(timezone.utc).isoformat())
        db.add(like)
        result2 = await db.execute(select(Post).where(Post.id == post_id))
        post = result2.scalar_one_or_none()
        if post:
            post.like_count = (post.like_count or 0) + 1
        await db.commit()


async def unlike_post(db: AsyncSession, user_id: uuid.UUID, post_id: uuid.UUID) -> None:
    result = await db.execute(select(PostLike).where(PostLike.user_id == user_id, PostLike.post_id == post_id))
    like = result.scalar_one_or_none()
    if like:
        await db.delete(like)
        result2 = await db.execute(select(Post).where(Post.id == post_id))
        post = result2.scalar_one_or_none()
        if post and post.like_count > 0:
            post.like_count -= 1
        await db.commit()


async def list_comments(db: AsyncSession, post_id: uuid.UUID, cursor: str | None, limit: int) -> PaginatedComments:
    query = select(PostComment).where(PostComment.post_id == post_id)
    if cursor:
        try:
            cur = _decode_cursor(cursor)
            query = query.where(PostComment.id > cur["id"])
        except Exception:
            pass
    query = query.order_by(PostComment.created_at.desc()).limit(limit + 1)
    result = await db.execute(query)
    comments = result.scalars().all()
    has_more = len(comments) > limit
    comments = comments[:limit]

    items = []
    for c in comments:
        user_r = await db.execute(select(User).where(User.id == c.user_id))
        u = user_r.scalar_one_or_none()
        from app.schemas.post import AuthorSnippet
        author = AuthorSnippet(id=u.id, name=u.name, avatar_url=u.avatar_url, is_verified=u.is_verified) if u else None
        items.append(CommentRead(id=c.id, user_id=c.user_id, body=c.body, created_at=c.created_at, author=author))

    next_cursor = _encode_cursor({"id": str(comments[-1].id)}) if has_more and comments else None
    return PaginatedComments(items=items, next_cursor=next_cursor)


async def add_comment(db: AsyncSession, user_id: uuid.UUID, post_id: uuid.UUID, body: str) -> CommentRead:
    from fastapi import HTTPException, status
    if not body.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Comment cannot be empty")
    comment = PostComment(post_id=post_id, user_id=user_id, body=body, created_at=datetime.now(timezone.utc).isoformat())
    db.add(comment)
    result = await db.execute(select(Post).where(Post.id == post_id))
    post = result.scalar_one_or_none()
    if post:
        post.comment_count = (post.comment_count or 0) + 1
    await db.commit()
    await db.refresh(comment)

    result = await db.execute(select(User).where(User.id == user_id))
    u = result.scalar_one()
    from app.schemas.post import AuthorSnippet
    author = AuthorSnippet(id=u.id, name=u.name, avatar_url=u.avatar_url, is_verified=u.is_verified)
    return CommentRead(id=comment.id, user_id=comment.user_id, body=comment.body, created_at=comment.created_at, author=author)


async def delete_comment(db: AsyncSession, user_id: uuid.UUID, post_id: uuid.UUID, comment_id: uuid.UUID) -> None:
    from fastapi import HTTPException, status
    result = await db.execute(select(PostComment).where(PostComment.id == comment_id, PostComment.post_id == post_id))
    comment = result.scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")

    result2 = await db.execute(select(Post).where(Post.id == post_id))
    post = result2.scalar_one_or_none()
    is_post_author = post and post.user_id == user_id

    if comment.user_id != user_id and not is_post_author:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")

    await db.delete(comment)
    if post and post.comment_count > 0:
        post.comment_count -= 1
    await db.commit()
