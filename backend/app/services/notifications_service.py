import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select, tuple_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import decode_cursor, encode_cursor
from app.models.notification import Notification
from app.models.user import User
from app.schemas.notification import NotificationRead, PaginatedNotifications
from app.schemas.post import AuthorSnippet


def notify(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    type: str,
    actor_id: uuid.UUID | None = None,
    post_id: uuid.UUID | None = None,
    place_id: uuid.UUID | None = None,
    message: str | None = None,
) -> None:
    """Queue a notification in the caller's transaction. No-op for self-actions."""
    if actor_id is not None and actor_id == user_id:
        return
    db.add(
        Notification(
            user_id=user_id,
            actor_id=actor_id,
            type=type,
            post_id=post_id,
            place_id=place_id,
            message=message,
            created_at=datetime.now(UTC),
        )
    )


async def list_notifications(
    db: AsyncSession, user_id: uuid.UUID, cursor: str | None, limit: int
) -> PaginatedNotifications:
    query = (
        select(Notification, User)
        .outerjoin(User, User.id == Notification.actor_id)
        .where(Notification.user_id == user_id)
    )
    if cursor:
        c = decode_cursor(cursor, t=datetime, id=uuid.UUID)
        query = query.where(
            tuple_(Notification.created_at, Notification.id) < tuple_(c["t"], c["id"])
        )
    query = query.order_by(
        Notification.created_at.desc(), Notification.id.desc()
    ).limit(limit + 1)
    rows = (await db.execute(query)).all()
    has_more = len(rows) > limit
    rows = rows[:limit]

    unread = (
        await db.execute(
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == user_id, Notification.read_at.is_(None))
        )
    ).scalar_one()

    items = [
        NotificationRead(
            id=n.id,
            type=n.type,
            actor=AuthorSnippet.model_validate(actor) if actor else None,
            post_id=n.post_id,
            place_id=n.place_id,
            message=n.message,
            is_read=n.read_at is not None,
            created_at=n.created_at,
        )
        for n, actor in rows
    ]
    next_cursor = None
    if has_more:
        last = rows[-1][0]
        next_cursor = encode_cursor(t=last.created_at, id=last.id)
    return PaginatedNotifications(
        items=items, next_cursor=next_cursor, unread_count=unread
    )


async def mark_all_read(db: AsyncSession, user_id: uuid.UUID) -> None:
    await db.execute(
        update(Notification)
        .where(Notification.user_id == user_id, Notification.read_at.is_(None))
        .values(read_at=datetime.now(UTC))
    )
    await db.commit()
