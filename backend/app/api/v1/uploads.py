from fastapi import APIRouter

from app.core.deps import CurrentUserID
from app.schemas.upload import PresignRequest, PresignResponse
from app.services import uploads_service

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.post("/presign", response_model=PresignResponse)
async def presign(_user_id: CurrentUserID, body: PresignRequest):
    return await uploads_service.presign_upload(body.filename, body.content_type, body.size)
