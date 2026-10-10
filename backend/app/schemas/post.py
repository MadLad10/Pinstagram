import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


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
    file_key: str = Field(pattern=r"^uploads/[0-9a-f-]{36}\.[a-z0-9]{1,5}$")
    media_type: Literal["image", "video"]
    caption: str | None = Field(None, max_length=2200)
    hashtags: list[str] | None = Field(None, max_length=30)
    price_mentioned: int | None = Field(None, ge=0)
    rating: int | None = Field(None, ge=1, le=5)

    @field_validator("hashtags")
    @classmethod
    def normalize_hashtags(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        tags = {t.strip().lstrip("#").lower() for t in v}
        return sorted(t for t in tags if t)


class CommentRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    body: str
    created_at: datetime
    author: AuthorSnippet | None = None

    model_config = {"from_attributes": True}


class CommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=1000)

    @field_validator("body")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Comment cannot be empty")
        return v.strip()


class PaginatedPosts(BaseModel):
    items: list[PostRead]
    next_cursor: str | None


class PaginatedComments(BaseModel):
    items: list[CommentRead]
    next_cursor: str | None
