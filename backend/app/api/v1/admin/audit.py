import uuid
from datetime import datetime

from fastapi import APIRouter, Query
from sqlalchemy import select, tuple_

from app.core.deps import DB, AdminUserID
from app.core.pagination import decode_cursor, encode_cursor
from app.models.report import AdminAction
from app.models.user import User

router = APIRouter()


@router.get("/audit-log")
async def audit_log(
    db: DB,
    _admin: AdminUserID,
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=100),
):
    query = select(AdminAction, User.name).join(User, User.id == AdminAction.admin_id)
    if cursor:
        c = decode_cursor(cursor, t=datetime, id=uuid.UUID)
        query = query.where(
            tuple_(AdminAction.created_at, AdminAction.id) < tuple_(c["t"], c["id"])
        )
    rows = (
        await db.execute(
            query.order_by(AdminAction.created_at.desc(), AdminAction.id.desc()).limit(
                limit + 1
            )
        )
    ).all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    return {
        "items": [
            {
                "id": str(a.id),
                "admin_id": str(a.admin_id),
                "admin_name": name,
                "action": a.action,
                "target_type": a.target_type,
                "target_id": str(a.target_id) if a.target_id else None,
                "metadata": a.metadata_,
                "created_at": a.created_at.isoformat(),
            }
            for a, name in rows
        ],
        "next_cursor": encode_cursor(t=rows[-1][0].created_at, id=rows[-1][0].id)
        if has_more
        else None,
    }
