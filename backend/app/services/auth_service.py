import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import httpx
from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy import select, update
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
from app.services.email_service import send_verification_code

log = logging.getLogger(__name__)

VERIFICATION_TTL = timedelta(minutes=15)
_DUMMY_HASH = hash_password(secrets.token_hex(16))


def _generate_code() -> str:
    return f"{secrets.randbelow(10**6):06d}"


def _issue_tokens(db: AsyncSession, user: User) -> TokenPair:
    """Create an access/refresh pair and stage the refresh token's hash."""
    raw_refresh = create_refresh_token(user.id)
    now = datetime.now(UTC)
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_token(raw_refresh),
            expires_at=now + timedelta(days=settings.JWT_REFRESH_TTL_DAYS),
            created_at=now,
        )
    )
    return TokenPair(
        access_token=create_access_token(user.id, user.role), refresh_token=raw_refresh
    )


def _stage_verification_code(db: AsyncSession, user: User) -> str:
    code = _generate_code()
    now = datetime.now(UTC)
    db.add(
        EmailVerification(
            user_id=user.id,
            code=code,
            expires_at=now + VERIFICATION_TTL,
            created_at=now,
        )
    )
    return code


async def signup(
    email: str, password: str, name: str, db: AsyncSession, background: BackgroundTasks
) -> AuthResponse:
    email = email.lower()
    existing = await db.execute(select(User.id).where(User.email == email))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
        )

    user = User(
        email=email, password_hash=hash_password(password), name=name, role="user"
    )
    db.add(user)
    await db.flush()
    code = _stage_verification_code(db, user)
    tokens = _issue_tokens(db, user)
    await db.commit()
    await db.refresh(user)

    background.add_task(send_verification_code, email, code)
    return AuthResponse(user=UserRead.model_validate(user), **tokens.model_dump())


async def login(email: str, password: str, db: AsyncSession) -> AuthResponse:
    user = (
        await db.execute(
            select(User).where(User.email == email.lower(), User.deleted_at.is_(None))
        )
    ).scalar_one_or_none()
    # Verify against a dummy hash when the user doesn't exist so response time
    # doesn't reveal which emails are registered.
    password_ok = verify_password(
        password, user.password_hash if user and user.password_hash else _DUMMY_HASH
    )
    if not user or not user.password_hash or not password_ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        )
    if user.banned_at:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Account suspended"
        )

    tokens = _issue_tokens(db, user)
    await db.commit()
    return AuthResponse(user=UserRead.model_validate(user), **tokens.model_dump())


async def google_auth(id_token: str, db: AsyncSession) -> AuthResponse:
    if not settings.GOOGLE_OAUTH_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Google sign-in not configured",
        )
    async with httpx.AsyncClient(timeout=5) as client:
        resp = await client.get(
            "https://oauth2.googleapis.com/tokeninfo", params={"id_token": id_token}
        )
    if resp.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Google token"
        )

    info = resp.json()
    if info.get("aud") != settings.GOOGLE_OAUTH_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token audience mismatch"
        )
    if info.get("email_verified") not in ("true", True):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Google email not verified"
        )

    google_id = info["sub"]
    email = info["email"].lower()
    user = (
        await db.execute(select(User).where(User.google_id == google_id))
    ).scalar_one_or_none()
    if not user:
        user = (
            await db.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()
        if user:
            user.google_id = google_id
            user.email_verified = True
        else:
            user = User(
                email=email,
                google_id=google_id,
                name=info.get("name") or email.split("@")[0],
                avatar_url=info.get("picture"),
                email_verified=True,
                role="user",
            )
            db.add(user)
            await db.flush()

    if user.deleted_at or user.banned_at:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Account suspended"
        )

    tokens = _issue_tokens(db, user)
    await db.commit()
    await db.refresh(user)
    return AuthResponse(user=UserRead.model_validate(user), **tokens.model_dump())


async def refresh_tokens(raw_refresh: str, db: AsyncSession) -> TokenPair:
    """Rotate a refresh token. Each token is single-use: presenting one that was
    already rotated means it leaked, so every session for that user is revoked."""
    now = datetime.now(UTC)
    rt = (
        await db.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == hash_token(raw_refresh)
            )
        )
    ).scalar_one_or_none()
    invalid = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token",
    )
    if not rt or rt.expires_at <= now:
        raise invalid
    if rt.revoked_at is not None:
        log.warning(
            "refresh token reuse detected for user %s; revoking all sessions",
            rt.user_id,
        )
        await revoke_all_sessions(db, rt.user_id)
        await db.commit()
        raise invalid

    rt.revoked_at = now
    user = (
        await db.execute(
            select(User).where(User.id == rt.user_id, User.deleted_at.is_(None))
        )
    ).scalar_one_or_none()
    if not user or user.banned_at:
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Account unavailable"
        )

    tokens = _issue_tokens(db, user)
    await db.commit()
    return tokens


async def revoke_all_sessions(db: AsyncSession, user_id: uuid.UUID) -> None:
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )


async def logout(user_id: uuid.UUID, raw_refresh: str | None, db: AsyncSession) -> None:
    if not raw_refresh:
        return
    await db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.token_hash == hash_token(raw_refresh),
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(UTC))
    )
    await db.commit()


async def verify_email(email: str, code: str, db: AsyncSession) -> bool:
    invalid = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired code"
    )
    user = (
        await db.execute(select(User).where(User.email == email.lower()))
    ).scalar_one_or_none()
    if not user:
        raise invalid  # same response as a wrong code: don't reveal registered emails
    if user.email_verified:
        return True

    now = datetime.now(UTC)
    verification = (
        await db.execute(
            select(EmailVerification).where(
                EmailVerification.user_id == user.id,
                EmailVerification.code == code,
                EmailVerification.used_at.is_(None),
                EmailVerification.expires_at > now,
            )
        )
    ).scalar_one_or_none()
    if not verification:
        raise invalid

    verification.used_at = now
    user.email_verified = True
    await db.commit()
    return True


async def resend_verification(
    user_id: uuid.UUID, db: AsyncSession, background: BackgroundTasks
) -> None:
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one()
    if user.email_verified:
        return
    # Invalidate outstanding codes so only the newest one works.
    await db.execute(
        update(EmailVerification)
        .where(
            EmailVerification.user_id == user.id, EmailVerification.used_at.is_(None)
        )
        .values(used_at=datetime.now(UTC))
    )
    code = _stage_verification_code(db, user)
    await db.commit()
    background.add_task(send_verification_code, user.email, code)
