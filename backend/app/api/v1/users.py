import uuid

from fastapi import APIRouter, Query

from app.core.deps import CurrentUserID, DB
from app.schemas.social import PaginatedUsers, UserProfile, UserUpdate
from app.schemas.auth import UserRead
from app.schemas.place import PaginatedPlaces
from app.services import social_service, auth_service
from app.models.user import User
from sqlalchemy import select

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)
async def get_me(user_id: CurrentUserID, db: DB):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one()
    return UserRead.model_validate(user)


@router.patch("/me", response_model=UserRead)
async def update_me(body: UserUpdate, user_id: CurrentUserID, db: DB):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one()
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(user, field, value)
    await db.commit()
    await db.refresh(user)
    return UserRead.model_validate(user)


@router.delete("/me", status_code=204)
async def delete_me(user_id: CurrentUserID, db: DB):
    from datetime import datetime, timezone
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one()
    user.deleted_at = datetime.now(timezone.utc)
    from app.models.refresh_token import RefreshToken
    rts = (await db.execute(select(RefreshToken).where(RefreshToken.user_id == user_id))).scalars().all()
    for rt in rts:
        rt.revoked_at = datetime.now(timezone.utc)
    await db.commit()


@router.get("/{user_id}", response_model=UserProfile)
async def get_user(user_id: uuid.UUID, db: DB, me: CurrentUserID):
    return await social_service.get_user_profile(db, user_id, me)


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
async def list_followers(user_id: uuid.UUID, db: DB, me: CurrentUserID, cursor: str | None = None, limit: int = Query(20, le=50)):
    return await social_service.list_followers(db, user_id, cursor, limit, me)


@router.get("/{user_id}/following", response_model=PaginatedUsers)
async def list_following(user_id: uuid.UUID, db: DB, me: CurrentUserID, cursor: str | None = None, limit: int = Query(20, le=50)):
    return await social_service.list_followers(db, user_id, cursor, limit, me)


@router.get("/me/saved-places", response_model=PaginatedPlaces)
async def saved_places(me: CurrentUserID, db: DB, cursor: str | None = None, limit: int = Query(20, le=50)):
    return await social_service.get_saved_places(db, me, cursor, limit)
