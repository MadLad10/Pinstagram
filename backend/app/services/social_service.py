import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.social import Block, Follow, SavedPlace
from app.models.place import Place
from app.models.user import User
from app.schemas.social import FollowerItem, PaginatedUsers, UserProfile


async def get_user_profile(db: AsyncSession, user_id: uuid.UUID, current_user_id: uuid.UUID | None = None) -> UserProfile:
    from fastapi import HTTPException, status
    result = await db.execute(select(User).where(User.id == user_id, User.deleted_at.is_(None)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    follower_count = (await db.execute(select(func.count()).where(Follow.followee_id == user_id))).scalar()
    following_count = (await db.execute(select(func.count()).where(Follow.follower_id == user_id))).scalar()
    from app.models.post import Post
    post_count = (await db.execute(select(func.count()).where(Post.user_id == user_id, Post.status == "published"))).scalar()

    is_following = False
    is_blocked = False
    if current_user_id and current_user_id != user_id:
        if user.is_private:
            follow_r = await db.execute(select(Follow).where(Follow.follower_id == current_user_id, Follow.followee_id == user_id))
            if not follow_r.scalar_one_or_none():
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This profile is private")
        follow_r = await db.execute(select(Follow).where(Follow.follower_id == current_user_id, Follow.followee_id == user_id))
        is_following = follow_r.scalar_one_or_none() is not None
        block_r = await db.execute(select(Block).where(Block.blocker_id == current_user_id, Block.blocked_id == user_id))
        is_blocked = block_r.scalar_one_or_none() is not None

    return UserProfile(
        id=user.id, name=user.name, bio=user.bio, avatar_url=user.avatar_url,
        location=user.location, is_private=user.is_private, is_verified=user.is_verified,
        role=user.role, follower_count=follower_count or 0, following_count=following_count or 0,
        post_count=post_count or 0, is_following=is_following, is_blocked=is_blocked,
        created_at=user.created_at,
    )


async def follow_user(db: AsyncSession, follower_id: uuid.UUID, followee_id: uuid.UUID) -> None:
    from fastapi import HTTPException, status
    if follower_id == followee_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot follow yourself")
    result = await db.execute(select(Follow).where(Follow.follower_id == follower_id, Follow.followee_id == followee_id))
    if not result.scalar_one_or_none():
        follow = Follow(follower_id=follower_id, followee_id=followee_id, created_at=datetime.now(timezone.utc).isoformat())
        db.add(follow)
        await db.commit()


async def unfollow_user(db: AsyncSession, follower_id: uuid.UUID, followee_id: uuid.UUID) -> None:
    result = await db.execute(select(Follow).where(Follow.follower_id == follower_id, Follow.followee_id == followee_id))
    follow = result.scalar_one_or_none()
    if follow:
        await db.delete(follow)
        await db.commit()


async def block_user(db: AsyncSession, blocker_id: uuid.UUID, blocked_id: uuid.UUID) -> None:
    result = await db.execute(select(Block).where(Block.blocker_id == blocker_id, Block.blocked_id == blocked_id))
    if not result.scalar_one_or_none():
        block = Block(blocker_id=blocker_id, blocked_id=blocked_id, created_at=datetime.now(timezone.utc).isoformat())
        db.add(block)
        await db.commit()


async def unblock_user(db: AsyncSession, blocker_id: uuid.UUID, blocked_id: uuid.UUID) -> None:
    result = await db.execute(select(Block).where(Block.blocker_id == blocker_id, Block.blocked_id == blocked_id))
    block = result.scalar_one_or_none()
    if block:
        await db.delete(block)
        await db.commit()


async def list_followers(db: AsyncSession, user_id: uuid.UUID, cursor: str | None, limit: int, current_user_id: uuid.UUID | None = None) -> PaginatedUsers:
    import base64, json
    query = select(User).join(Follow, Follow.follower_id == User.id).where(Follow.followee_id == user_id, User.deleted_at.is_(None))
    if cursor:
        try:
            cur = json.loads(base64.b64decode(cursor).decode())
            query = query.where(User.id > cur["id"])
        except Exception:
            pass
    query = query.limit(limit + 1)
    result = await db.execute(query)
    users = result.scalars().all()
    has_more = len(users) > limit
    users = users[:limit]
    items = [FollowerItem(id=u.id, name=u.name, avatar_url=u.avatar_url, bio=u.bio, is_verified=u.is_verified) for u in users]
    next_cursor = base64.b64encode(json.dumps({"id": str(users[-1].id)}).encode()).decode() if has_more else None
    return PaginatedUsers(items=items, next_cursor=next_cursor)


async def get_saved_places(db: AsyncSession, user_id: uuid.UUID, cursor: str | None, limit: int):
    import base64, json
    from app.schemas.place import PaginatedPlaces, PlaceSummary
    query = select(Place).join(SavedPlace, SavedPlace.place_id == Place.id).where(SavedPlace.user_id == user_id)
    if cursor:
        try:
            cur = json.loads(base64.b64decode(cursor).decode())
            query = query.where(Place.id > cur["id"])
        except Exception:
            pass
    query = query.limit(limit + 1)
    result = await db.execute(query)
    places = result.scalars().all()
    has_more = len(places) > limit
    places = places[:limit]
    items = [PlaceSummary.model_validate(p) for p in places]
    next_cursor = base64.b64encode(json.dumps({"id": str(places[-1].id)}).encode()).decode() if has_more else None
    return PaginatedPlaces(items=items, next_cursor=next_cursor)
