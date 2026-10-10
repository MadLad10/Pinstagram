import uuid
from datetime import UTC, datetime
from typing import TypeVar

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base
from app.models.report import AdminAction

M = TypeVar("M", bound=Base)


async def get_or_404(db: AsyncSession, model: type[M], obj_id: uuid.UUID) -> M:
    obj = (
        await db.execute(select(model).where(model.id == obj_id))
    ).scalar_one_or_none()
    if obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"{model.__name__} not found"
        )
    return obj


def log_action(
    db: AsyncSession,
    admin_id: uuid.UUID,
    action: str,
    target_type: str | None = None,
    target_id: uuid.UUID | None = None,
    metadata: dict | None = None,
) -> None:
    """Stage an audit-log entry in the caller's transaction, so the log and
    the action it describes commit (or roll back) together."""
    db.add(
        AdminAction(
            admin_id=admin_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            metadata_=metadata,
            created_at=datetime.now(UTC),
        )
    )
