import re
import uuid
from datetime import UTC, datetime, timedelta

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import HTTPException, status
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.schemas.upload import PresignResponse

MAX_SIZE = 50 * 1024 * 1024  # 50 MB
PRESIGN_TTL_S = 900  # 15 min
ALLOWED_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "video/mp4": "mp4",
    "video/quicktime": "mov",
}


def s3_client(endpoint: str | None = None):
    return boto3.client(
        "s3",
        endpoint_url=endpoint or settings.S3_ENDPOINT,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        region_name=settings.S3_REGION,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def _require_uploads() -> None:
    if not settings.UPLOADS_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Photo uploads aren't enabled on this demo yet",
        )


async def presign_upload(
    filename: str, content_type: str, size: int
) -> PresignResponse:
    _require_uploads()
    if content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {content_type}",
        )
    if size > MAX_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="File too large (max 50 MB)"
        )

    # The key is server-generated; only a sanitized extension comes from the client.
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if not re.fullmatch(r"[a-z0-9]{1,5}", ext):
        ext = ALLOWED_TYPES[content_type]
    file_key = f"uploads/{uuid.uuid4()}.{ext}"

    # Sign against the public URL: the signature covers the Host header the
    # client will actually send.
    def _sign() -> str:
        return s3_client(settings.s3_public_base).generate_presigned_url(
            "put_object",
            Params={
                "Bucket": settings.S3_BUCKET,
                "Key": file_key,
                "ContentType": content_type,
            },
            ExpiresIn=PRESIGN_TTL_S,
        )

    try:
        upload_url = await run_in_threadpool(_sign)
    except (ClientError, BotoCoreError):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not generate upload URL",
        ) from None

    return PresignResponse(
        upload_url=upload_url,
        file_key=file_key,
        expires_at=datetime.now(UTC) + timedelta(seconds=PRESIGN_TTL_S),
    )


def ensure_bucket_exists() -> None:
    s3 = s3_client()
    try:
        s3.head_bucket(Bucket=settings.S3_BUCKET)
    except ClientError:
        s3.create_bucket(Bucket=settings.S3_BUCKET)
