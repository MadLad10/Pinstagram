import random
import string
import uuid
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.models.email_verification import EmailVerification
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.auth import AuthResponse, TokenPair, UserRead


def _user_to_read(user: User) -> UserRead:
    return UserRead.model_validate(user)


def _generate_code() -> str:
    return "".join(random.choices(string.digits, k=6))


async def signup(email: str, password: str, name: str, db: AsyncSession) -> AuthResponse:
    result = await db.execute(select(User).where(User.email == email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        email=email,
        password_hash=hash_password(password),
        name=name,
        email_verified=False,
        role="user",
    )
    db.add(user)
    await db.flush()

    code = _generate_code()
    verification = EmailVerification(
        user_id=user.id,
        code=code,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
        created_at=datetime.now(timezone.utc),
    )
    db.add(verification)

    access_token = create_access_token(user.id, user.role)
    raw_refresh = create_refresh_token(user.id)

    rt = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(raw_refresh),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.JWT_REFRESH_TTL_DAYS),
        created_at=datetime.now(timezone.utc),
    )
    db.add(rt)
    await db.commit()
    await db.refresh(user)

    return AuthResponse(user=_user_to_read(user), access_token=access_token, refresh_token=raw_refresh)


async def login(email: str, password: str, db: AsyncSession) -> AuthResponse:
    result = await db.execute(select(User).where(User.email == email, User.deleted_at.is_(None)))
    user = result.scalar_one_or_none()
    if not user or not user.password_hash or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    if user.banned_at:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account suspended")

    access_token = create_access_token(user.id, user.role)
    raw_refresh = create_refresh_token(user.id)
    rt = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(raw_refresh),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.JWT_REFRESH_TTL_DAYS),
        created_at=datetime.now(timezone.utc),
    )
    db.add(rt)
    await db.commit()
    return AuthResponse(user=_user_to_read(user), access_token=access_token, refresh_token=raw_refresh)


async def google_auth(id_token: str, db: AsyncSession) -> AuthResponse:
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"https://oauth2.googleapis.com/tokeninfo?id_token={id_token}")
    if resp.status_code != 200:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Google token")

    info = resp.json()
    if info.get("aud") != settings.GOOGLE_OAUTH_CLIENT_ID:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token audience mismatch")

    google_id = info["sub"]
    email = info.get("email", "")
    name = info.get("name", email.split("@")[0])

    result = await db.execute(select(User).where(User.google_id == google_id))
    user = result.scalar_one_or_none()

    if not user:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user:
            user.google_id = google_id
            user.email_verified = True
        else:
            user = User(email=email, google_id=google_id, name=name, email_verified=True, role="user")
            db.add(user)
            await db.flush()

    if user.banned_at:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account suspended")

    access_token = create_access_token(user.id, user.role)
    raw_refresh = create_refresh_token(user.id)
    rt = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(raw_refresh),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.JWT_REFRESH_TTL_DAYS),
        created_at=datetime.now(timezone.utc),
    )
    db.add(rt)
    await db.commit()
    await db.refresh(user)
    return AuthResponse(user=_user_to_read(user), access_token=access_token, refresh_token=raw_refresh)


async def refresh_tokens(raw_refresh: str, db: AsyncSession) -> TokenPair:
    token_hash = hash_token(raw_refresh)
    now = datetime.now(timezone.utc)

    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked_at.is_(None),
            RefreshToken.expires_at > now,
        )
    )
    rt = result.scalar_one_or_none()
    if not rt:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")

    rt.revoked_at = now

    result = await db.execute(select(User).where(User.id == rt.user_id, User.deleted_at.is_(None)))
    user = result.scalar_one_or_none()
    if not user or user.banned_at:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account unavailable")

    new_access = create_access_token(user.id, user.role)
    new_raw_refresh = create_refresh_token(user.id)
    new_rt = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(new_raw_refresh),
        expires_at=now + timedelta(days=settings.JWT_REFRESH_TTL_DAYS),
        created_at=now,
    )
    db.add(new_rt)
    await db.commit()
    return TokenPair(access_token=new_access, refresh_token=new_raw_refresh)


async def logout(user_id: uuid.UUID, raw_refresh: str | None, db: AsyncSession) -> None:
    if raw_refresh:
        token_hash = hash_token(raw_refresh)
        result = await db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash, RefreshToken.user_id == user_id)
        )
        rt = result.scalar_one_or_none()
        if rt:
            rt.revoked_at = datetime.now(timezone.utc)
            await db.commit()


async def verify_email(email: str, code: str, db: AsyncSession) -> bool:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(EmailVerification).where(
            EmailVerification.user_id == user.id,
            EmailVerification.code == code,
            EmailVerification.used_at.is_(None),
            EmailVerification.expires_at > now,
        )
    )
    verification = result.scalar_one_or_none()
    if not verification:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired code")

    verification.used_at = now
    user.email_verified = True
    await db.commit()
    return True
