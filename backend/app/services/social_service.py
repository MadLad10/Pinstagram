import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import delete, func, or_, select, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import decode_cursor, encode_cursor
from app.models.place import Place
from app.models.post import Post
from app.models.social import Block, Follow, SavedPlace
from app.models.user import User
from app.schemas.place import PaginatedPlaces, PlaceSummary
from app.schemas.social import FollowerItem, PaginatedUsers, UserProfile
from app.services import notifications_service


async def _active_user_or_404(db: AsyncSession, user_id: uuid.UUID) -> User:
    user = (
        await db.execute(
            select(User).where(User.id == user_id, User.deleted_at.is_(None))
        )
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return user


async def _exists(db: AsyncSession, stmt) -> bool:
    return (await db.execute(select(stmt.exists()))).scalar_one()


async def get_user_profile(
    db: AsyncSession, user_id: uuid.UUID, viewer_id: uuid.UUID | None = None
) -> UserProfile:
    user = await _active_user_or_404(db, user_id)

    is_following = is_blocked = False
    if viewer_id and viewer_id != user_id:
        is_following = await _exists(
            db,
            select(Follow).where(
                Follow.follower_id == viewer_id, Follow.followee_id == user_id
            ),
        )
        is_blocked = await _exists(
            db,
            select(Block).where(
                Block.blocker_id == viewer_id, Block.blocked_id == user_id
            ),
        )
        if user.is_private and not is_following:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="This profile is private"
            )

    def _count(stmt):
        return select(func.count()).select_from(stmt.subquery()).scalar_subquery()

    follower_count, following_count, post_count = (
        await db.execute(
            select(
                _count(select(Follow.follower_id).where(Follow.followee_id == user_id)),
                _count(select(Follow.followee_id).where(Follow.follower_id == user_id)),
                _count(
                    select(Post.id).where(
                        Post.user_id == user_id, Post.status == "published"
                    )
                ),
            )
        )
    ).one()

    return UserProfile(
        id=user.id,
        name=user.name,
        bio=user.bio,
        avatar_url=user.avatar_url,
        location=user.location,
        is_private=user.is_private,
        is_verified=user.is_verified,
        role=user.role,
        follower_count=follower_count,
        following_count=following_count,
        post_count=post_count,
        is_following=is_following,
        is_blocked=is_blocked,
        created_at=user.created_at,
    )


async def follow_user(
    db: AsyncSession, follower_id: uuid.UUID, followee_id: uuid.UUID
) -> None:
    if follower_id == followee_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot follow yourself"
        )
    await _active_user_or_404(db, followee_id)
    blocked = await _exists(
        db,
        select(Block).where(
            or_(
                (Block.blocker_id == followee_id) & (Block.blocked_id == follower_id),
                (Block.blocker_id == follower_id) & (Block.blocked_id == followee_id),
            )
        ),
    )
    if blocked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Cannot follow this user"
        )

    inserted = (
        await db.execute(
            insert(Follow)
            .values(
                follower_id=follower_id,
                followee_id=followee_id,
                created_at=datetime.now(UTC),
            )
            .on_conflict_do_nothing()
            .returning(Follow.follower_id)
        )
    ).first()
    if inserted:
        notifications_service.notify(
            db, user_id=followee_id, actor_id=follower_id, type="follow"
        )
    await db.commit()


async def unfollow_user(
    db: AsyncSession, follower_id: uuid.UUID, followee_id: uuid.UUID
) -> None:
    await db.execute(
        delete(Follow).where(
            Follow.follower_id == follower_id, Follow.followee_id == followee_id
        )
    )
    await db.commit()


async def block_user(
    db: AsyncSession, blocker_id: uuid.UUID, blocked_id: uuid.UUID
) -> None:
    if blocker_id == blocked_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot block yourself"
        )
    await _active_user_or_404(db, blocked_id)
    await db.execute(
        insert(Block)
        .values(
            blocker_id=blocker_id, blocked_id=blocked_id, created_at=datetime.now(UTC)
        )
        .on_conflict_do_nothing()
    )
    # Blocking severs the follow relationship in both directions.
    await db.execute(
        delete(Follow).where(
            or_(
                (Follow.follower_id == blocker_id) & (Follow.followee_id == blocked_id),
                (Follow.follower_id == blocked_id) & (Follow.followee_id == blocker_id),
            )
        )
    )
    await db.commit()


async def unblock_user(
    db: AsyncSession, blocker_id: uuid.UUID, blocked_id: uuid.UUID
) -> None:
    await db.execute(
        delete(Block).where(
            Block.blocker_id == blocker_id, Block.blocked_id == blocked_id
        )
    )
    await db.commit()


async def _list_follow_edges(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    direction: str,
    cursor: str | None,
    limit: int,
    viewer_id: uuid.UUID | None,
) -> PaginatedUsers:
    """direction="followers": people who follow user_id.
    direction="following": people user_id follows."""
    if direction == "followers":
        other, anchor = Follow.follower_id, Follow.followee_id
    else:
        other, anchor = Follow.followee_id, Follow.follower_id

    query = (
        select(User, Follow.created_at)
        .join(Follow, other == User.id)
        .where(anchor == user_id, User.deleted_at.is_(None))
    )
    if cursor:
        c = decode_cursor(cursor, t=datetime, id=uuid.UUID)
        query = query.where(
            tuple_(Follow.created_at, User.id) < tuple_(c["t"], c["id"])
        )
    query = query.order_by(Follow.created_at.desc(), User.id.desc()).limit(limit + 1)

    rows = (await db.execute(query)).all()
    has_more = len(rows) > limit
    rows = rows[:limit]

    viewer_follows: set[uuid.UUID] = set()
    if viewer_id and rows:
        viewer_follows = set(
            (
                await db.execute(
                    select(Follow.followee_id).where(
                        Follow.follower_id == viewer_id,
                        Follow.followee_id.in_([u.id for u, _ in rows]),
                    )
                )
            ).scalars()
        )

    items = [
        FollowerItem(
            id=u.id,
            name=u.name,
            avatar_url=u.avatar_url,
            bio=u.bio,
            is_verified=u.is_verified,
            is_following=u.id in viewer_follows,
        )
        for u, _ in rows
    ]
    next_cursor = encode_cursor(t=rows[-1][1], id=rows[-1][0].id) if has_more else None
    return PaginatedUsers(items=items, next_cursor=next_cursor)


async def list_followers(db, user_id, cursor, limit, viewer_id=None) -> PaginatedUsers:
    return await _list_follow_edges(
        db,
        user_id=user_id,
        direction="followers",
        cursor=cursor,
        limit=limit,
        viewer_id=viewer_id,
    )


async def list_following(db, user_id, cursor, limit, viewer_id=None) -> PaginatedUsers:
    return await _list_follow_edges(
        db,
        user_id=user_id,
        direction="following",
        cursor=cursor,
        limit=limit,
        viewer_id=viewer_id,
    )


async def get_saved_places(
    db: AsyncSession, user_id: uuid.UUID, cursor: str | None, limit: int
) -> PaginatedPlaces:
    query = (
        select(Place, SavedPlace.created_at)
        .join(SavedPlace, SavedPlace.place_id == Place.id)
        .where(SavedPlace.user_id == user_id)
    )
    if cursor:
        c = decode_cursor(cursor, t=datetime, id=uuid.UUID)
        query = query.where(
            tuple_(SavedPlace.created_at, Place.id) < tuple_(c["t"], c["id"])
        )
    query = query.order_by(SavedPlace.created_at.desc(), Place.id.desc()).limit(
        limit + 1
    )

    rows = (await db.execute(query)).all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = encode_cursor(t=rows[-1][1], id=rows[-1][0].id) if has_more else None
    return PaginatedPlaces(
        items=[PlaceSummary.model_validate(p) for p, _ in rows], next_cursor=next_cursor
    )
