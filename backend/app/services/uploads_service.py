import uuid
from datetime import datetime, timedelta, timezone

import boto3
from botocore.exceptions import ClientError
from fastapi import HTTPException, status

from app.core.config import settings
from app.schemas.upload import PresignResponse

MAX_SIZE = 50 * 1024 * 1024  # 50 MB
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "video/mp4", "video/quicktime"}


def _s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        region_name=settings.S3_REGION,
    )


async def presign_upload(filename: str, content_type: str, size: int) -> PresignResponse:
    if content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unsupported file type: {content_type}")
    if size > MAX_SIZE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File too large (max 50 MB)")

    ext = filename.rsplit(".", 1)[-1] if "." in filename else "bin"
    file_key = f"uploads/{uuid.uuid4()}.{ext}"
    expires_in = 900  # 15 min

    s3 = _s3_client()
    try:
        upload_url = s3.generate_presigned_url(
            "put_object",
            Params={"Bucket": settings.S3_BUCKET, "Key": file_key, "ContentType": content_type},
            ExpiresIn=expires_in,
        )
    except ClientError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not generate upload URL")

    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    return PresignResponse(upload_url=upload_url, file_key=file_key, expires_at=expires_at)


def ensure_bucket_exists():
    s3 = _s3_client()
    try:
        s3.head_bucket(Bucket=settings.S3_BUCKET)
    except ClientError:
        s3.create_bucket(Bucket=settings.S3_BUCKET)
