import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.db.session import get_db

bearer = HTTPBearer(auto_error=False)


def _claims(credentials: HTTPAuthorizationCredentials | None) -> dict:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_token(credentials.credentials)
        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type"
            )
        uuid.UUID(payload["sub"])
        return payload
    except (JWTError, KeyError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from None


async def get_current_user_id(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> uuid.UUID:
    return uuid.UUID(_claims(credentials)["sub"])


async def get_optional_user_id(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> uuid.UUID | None:
    """Like get_current_user_id, but anonymous requests get None instead of 401.
    An invalid token is still rejected."""
    if credentials is None:
        return None
    return uuid.UUID(_claims(credentials)["sub"])


async def require_admin(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> uuid.UUID:
    payload = _claims(credentials)
    if payload.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required"
        )
    return uuid.UUID(payload["sub"])


CurrentUserID = Annotated[uuid.UUID, Depends(get_current_user_id)]
OptionalUserID = Annotated[uuid.UUID | None, Depends(get_optional_user_id)]
AdminUserID = Annotated[uuid.UUID, Depends(require_admin)]
DB = Annotated[AsyncSession, Depends(get_db)]
