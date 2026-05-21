import uuid
from io import BytesIO
from pathlib import Path
from typing import BinaryIO

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import get_settings


def upload_cv(file_obj: BinaryIO, filename: str) -> str:
    settings = get_settings()
    ext = ''
    if '.' in filename:
        ext = filename[filename.rfind('.') :]
    key = f"cvs/{uuid.uuid4().hex}{ext}"
    file_obj.seek(0)
    raw = file_obj.read()

    # Dev fallback: if S3 is not available, persist under local uploads.
    if not settings.s3_access_key or not settings.s3_secret_key:
        return save_cv_local(BytesIO(raw), key)

    s3 = boto3.client(
        's3',
        endpoint_url=settings.s3_endpoint_url,
        region_name=settings.s3_region,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
    )

    try:
        s3.upload_fileobj(BytesIO(raw), settings.s3_bucket, key)
    except (BotoCoreError, ClientError, Exception):
        return save_cv_local(BytesIO(raw), key)

    if settings.s3_public_url_base:
        return f"{settings.s3_public_url_base.rstrip('/')}/{key}"

    return s3.generate_presigned_url('get_object', Params={'Bucket': settings.s3_bucket, 'Key': key}, ExpiresIn=3600)


def upload_document(file_obj: BinaryIO, filename: str, prefix: str = 'documents') -> str:
    settings = get_settings()
    ext = ''
    if '.' in filename:
        ext = filename[filename.rfind('.') :]
    key = f"{prefix}/{uuid.uuid4().hex}{ext}"
    file_obj.seek(0)
    raw = file_obj.read()

    if not settings.s3_access_key or not settings.s3_secret_key:
        return save_cv_local(BytesIO(raw), key)

    s3 = boto3.client(
        's3',
        endpoint_url=settings.s3_endpoint_url,
        region_name=settings.s3_region,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
    )

    try:
        s3.upload_fileobj(BytesIO(raw), settings.s3_bucket, key)
    except (BotoCoreError, ClientError, Exception):
        return save_cv_local(BytesIO(raw), key)

    if settings.s3_public_url_base:
        return f"{settings.s3_public_url_base.rstrip('/')}/{key}"

    return s3.generate_presigned_url('get_object', Params={'Bucket': settings.s3_bucket, 'Key': key}, ExpiresIn=3600)


def save_cv_local(file_obj: BinaryIO, key: str) -> str:
    file_obj.seek(0)
    base_dir = Path(__file__).resolve().parents[2]
    uploads_dir = base_dir / 'uploads'
    full_path = uploads_dir / key
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_bytes(file_obj.read())
    return f"/uploads/{key}"
