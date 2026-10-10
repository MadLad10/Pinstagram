import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.post import AuthorSnippet


class NotificationRead(BaseModel):
    id: uuid.UUID
    type: str
    actor: AuthorSnippet | None
    post_id: uuid.UUID | None
    place_id: uuid.UUID | None
    message: str | None
    is_read: bool
    created_at: datetime


class PaginatedNotifications(BaseModel):
    items: list[NotificationRead]
    next_cursor: str | None
    unread_count: int
