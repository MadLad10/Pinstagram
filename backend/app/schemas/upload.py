from datetime import datetime

from pydantic import BaseModel


class PresignRequest(BaseModel):
    filename: str
    content_type: str
    size: int


class PresignResponse(BaseModel):
    upload_url: str
    file_key: str
    expires_at: datetime
