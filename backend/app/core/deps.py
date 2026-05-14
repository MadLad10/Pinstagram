import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.db.session import get_db

bearer = HTTPBearer()


async def get_current_user_id(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer)],
) -> uuid.UUID:
    token = credentials.credentials
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
        return uuid.UUID(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")


async def get_current_user_role(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer)],
) -> tuple[uuid.UUID, str]:
    token = credentials.credentials
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
        return uuid.UUID(payload["sub"]), payload["role"]
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")


async def require_admin(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer)],
) -> uuid.UUID:
    user_id, role = await get_current_user_role(credentials)
    if role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user_id


CurrentUserID = Annotated[uuid.UUID, Depends(get_current_user_id)]
AdminUserID = Annotated[uuid.UUID, Depends(require_admin)]
DB = Annotated[AsyncSession, Depends(get_db)]
