from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from app.core.deps import DB, CurrentUserID
from app.core.rate_limit import hit, rate_limit
from app.schemas.auth import (
    AuthResponse,
    GoogleAuthRequest,
    LoginRequest,
    RefreshRequest,
    SignupRequest,
    TokenPair,
    VerifyEmailRequest,
)
from app.services import auth_service

# API.md: auth endpoints are limited to 10 requests/min per IP.
router = APIRouter(
    prefix="/auth", tags=["auth"], dependencies=[Depends(rate_limit("auth", 10, 60))]
)


@router.post("/signup", response_model=AuthResponse, status_code=201)
async def signup(body: SignupRequest, db: DB, background: BackgroundTasks):
    return await auth_service.signup(
        body.email, body.password, body.name, db, background
    )


@router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest, db: DB):
    return await auth_service.login(body.email, body.password, db)


@router.post("/google", response_model=AuthResponse)
async def google_auth(body: GoogleAuthRequest, db: DB):
    return await auth_service.google_auth(body.id_token, db)


@router.post("/refresh", response_model=TokenPair)
async def refresh(body: RefreshRequest, db: DB):
    return await auth_service.refresh_tokens(body.refresh_token, db)


@router.post("/logout", status_code=204)
async def logout(user_id: CurrentUserID, db: DB, body: RefreshRequest | None = None):
    await auth_service.logout(user_id, body.refresh_token if body else None, db)


@router.post("/verify-email")
async def verify_email(body: VerifyEmailRequest, db: DB):
    # A 6-digit code is brute-forceable without a per-account attempt cap.
    if await hit(f"verify:{body.email.lower()}", 5, 15 * 60):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts, request a new code later",
        )
    return {"verified": await auth_service.verify_email(body.email, body.code, db)}


@router.post("/resend-verification", status_code=204)
async def resend_verification(
    user_id: CurrentUserID, db: DB, background: BackgroundTasks
):
    await auth_service.resend_verification(user_id, db, background)
