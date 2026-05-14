from fastapi import APIRouter, BackgroundTasks, Body

from app.core.deps import CurrentUserID, DB
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

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=AuthResponse, status_code=201)
async def signup(body: SignupRequest, db: DB, background_tasks: BackgroundTasks):
    return await auth_service.signup(body.email, body.password, body.name, db)


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
    raw = body.refresh_token if body else None
    await auth_service.logout(user_id, raw, db)


@router.post("/verify-email")
async def verify_email(body: VerifyEmailRequest, db: DB):
    verified = await auth_service.verify_email(body.email, body.code, db)
    return {"verified": verified}
