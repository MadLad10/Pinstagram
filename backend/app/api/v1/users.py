import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.core.config import settings
from app.core.deps import DB, CurrentUserID, OptionalUserID
from app.models.user import User
from app.schemas.auth import UserRead
from app.schemas.place import PaginatedPlaces
from app.schemas.post import PaginatedPosts
from app.schemas.social import PaginatedUsers, UserProfile, UserUpdate
from app.services import auth_service, posts_service, social_service

router = APIRouter(prefix="/users", tags=["users"])

Limit = Query(20, ge=1, le=50)


async def _me(db: DB, user_id: uuid.UUID) -> User:
    return (await db.execute(select(User).where(User.id == user_id))).scalar_one()


def _forbid_demo_account(user: User) -> None:
    if settings.DEMO_USER_EMAIL and user.email == settings.DEMO_USER_EMAIL:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This action is disabled for the shared demo account",
        )


@router.get("/me", response_model=UserRead)
async def get_me(user_id: CurrentUserID, db: DB):
    return UserRead.model_validate(await _me(db, user_id))


@router.patch("/me", response_model=UserRead)
async def update_me(body: UserUpdate, user_id: CurrentUserID, db: DB):
    user = await _me(db, user_id)
    _forbid_demo_account(user)
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(user, field, value)
    await db.commit()
    await db.refresh(user)
    return UserRead.model_validate(user)


@router.delete("/me", status_code=204)
async def delete_me(user_id: CurrentUserID, db: DB):
    user = await _me(db, user_id)
    _forbid_demo_account(user)
    user.deleted_at = datetime.now(UTC)
    await auth_service.revoke_all_sessions(db, user_id)
    await db.commit()


@router.get("/me/saved-places", response_model=PaginatedPlaces)
async def saved_places(
    me: CurrentUserID, db: DB, cursor: str | None = None, limit: int = Limit
):
    return await social_service.get_saved_places(db, me, cursor, limit)


@router.get("/{user_id}", response_model=UserProfile)
async def get_user(user_id: uuid.UUID, db: DB, me: OptionalUserID):
    return await social_service.get_user_profile(db, user_id, me)


@router.get("/{user_id}/posts", response_model=PaginatedPosts)
async def user_posts(
    user_id: uuid.UUID,
    db: DB,
    me: OptionalUserID,
    cursor: str | None = None,
    limit: int = Limit,
):
    await social_service.get_user_profile(db, user_id, me)  # enforces privacy / 404
    return await posts_service.list_user_posts(db, user_id, me, cursor, limit)


@router.post("/{user_id}/follow", status_code=204)
async def follow(user_id: uuid.UUID, me: CurrentUserID, db: DB):
    await social_service.follow_user(db, me, user_id)


@router.delete("/{user_id}/follow", status_code=204)
async def unfollow(user_id: uuid.UUID, me: CurrentUserID, db: DB):
    await social_service.unfollow_user(db, me, user_id)


@router.post("/{user_id}/block", status_code=204)
async def block(user_id: uuid.UUID, me: CurrentUserID, db: DB):
    await social_service.block_user(db, me, user_id)


@router.delete("/{user_id}/block", status_code=204)
async def unblock(user_id: uuid.UUID, me: CurrentUserID, db: DB):
    await social_service.unblock_user(db, me, user_id)


@router.get("/{user_id}/followers", response_model=PaginatedUsers)
async def list_followers(
    user_id: uuid.UUID,
    db: DB,
    me: OptionalUserID,
    cursor: str | None = None,
    limit: int = Limit,
):
    return await social_service.list_followers(db, user_id, cursor, limit, me)


@router.get("/{user_id}/following", response_model=PaginatedUsers)
async def list_following(
    user_id: uuid.UUID,
    db: DB,
    me: OptionalUserID,
    cursor: str | None = None,
    limit: int = Limit,
):
    return await social_service.list_following(db, user_id, cursor, limit, me)
