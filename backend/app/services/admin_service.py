import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.report import AdminAction


async def log_action(
    db: AsyncSession,
    admin_id: uuid.UUID,
    action: str,
    target_type: str | None = None,
    target_id: uuid.UUID | None = None,
    metadata: dict | None = None,
) -> None:
    entry = AdminAction(
        admin_id=admin_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        metadata_=metadata,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    db.add(entry)
    await db.commit()
