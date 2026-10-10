import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class UserProfile(BaseModel):
    id: uuid.UUID
    name: str
    bio: str | None
    avatar_url: str | None
    location: str | None
    is_private: bool
    is_verified: bool
    role: str
    follower_count: int = 0
    following_count: int = 0
    post_count: int = 0
    is_following: bool = False
    is_blocked: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    bio: str | None = Field(None, max_length=300)
    avatar_url: str | None = None
    location: str | None = None
    is_private: bool | None = None


class FollowerItem(BaseModel):
    id: uuid.UUID
    name: str
    avatar_url: str | None
    bio: str | None
    is_verified: bool
    is_following: bool = False

    model_config = {"from_attributes": True}


class PaginatedUsers(BaseModel):
    items: list[FollowerItem]
    next_cursor: str | None


class ReportCreate(BaseModel):
    target_type: Literal["post", "review", "comment", "user"]
    target_id: uuid.UUID
    reason: Literal[
        "nudity", "hate", "violence", "spam", "wrong_location", "fake_review", "other"
    ]
    notes: str | None = Field(None, max_length=1000)
