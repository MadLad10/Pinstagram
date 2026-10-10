from datetime import datetime

from pydantic import BaseModel, Field


class PresignRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str
    size: int = Field(gt=0)


class PresignResponse(BaseModel):
    upload_url: str
    file_key: str
    expires_at: datetime
