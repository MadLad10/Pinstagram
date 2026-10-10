from typing import Literal

from pydantic import BaseModel, Field


class ReasonBody(BaseModel):
    reason: str | None = Field(None, max_length=1000)


class ResolveReportBody(BaseModel):
    action: Literal["remove_content", "ban_user", "dismiss"] = "dismiss"
    notes: str | None = Field(None, max_length=1000)


class PromoteBody(BaseModel):
    role: Literal["user", "business", "creator", "admin"] = "admin"
