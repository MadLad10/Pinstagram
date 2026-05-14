import uuid
from datetime import datetime

from pydantic import BaseModel


class AuthorSnippet(BaseModel):
    id: uuid.UUID
    name: str
    avatar_url: str | None
    is_verified: bool

    model_config = {"from_attributes": True}


class PlaceSnippet(BaseModel):
    id: uuid.UUID
    name: str
    category: str
    area: str | None
    district: str | None
    avg_rating: float

    model_config = {"from_attributes": True}


class PostRead(BaseModel):
    id: uuid.UUID
    media_url: str
    media_type: str
    thumbnail_url: str | None
    caption: str | None
    hashtags: list[str] | None
    price_mentioned: int | None
    rating: int | None
    status: str
    like_count: int
    comment_count: int
    is_liked_by_me: bool = False
    is_saved_by_me: bool = False
    author: AuthorSnippet
    place: PlaceSnippet
    created_at: datetime

    model_config = {"from_attributes": True}


class PostCreate(BaseModel):
    place_id: uuid.UUID
    file_key: str
    media_type: str
    caption: str | None = None
    hashtags: list[str] | None = None
    price_mentioned: int | None = None
    rating: int | None = None


class CommentRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    body: str
    created_at: str
    author: AuthorSnippet | None = None

    model_config = {"from_attributes": True}


class CommentCreate(BaseModel):
    body: str


class PaginatedPosts(BaseModel):
    items: list[PostRead]
    next_cursor: str | None


class PaginatedComments(BaseModel):
    items: list[CommentRead]
    next_cursor: str | None
