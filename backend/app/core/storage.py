import uuid
from pathlib import Path
from typing import BinaryIO
from urllib.parse import urlparse

import boto3
from botocore.config import Config

from app.core.config import settings


def _local_storage_root() -> Path:
    endpoint = settings.S3_ENDPOINT_URL or ""
    parsed = urlparse(endpoint)
    if parsed.scheme == "file":
        path = parsed.path or "/app/storage"
        return Path(path)
    return Path("/app/storage")


def is_local_storage() -> bool:
    endpoint = settings.S3_ENDPOINT_URL or ""
    return endpoint.startswith("file://")


def _local_path(key: str) -> Path:
    return _local_storage_root() / settings.S3_BUCKET / key


def _get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT_URL,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        config=Config(signature_version="s3v4"),
    )


def upload_book(file: BinaryIO, user_id: str, filename: str) -> str:
    safe_name = Path(filename).name
    key = f"books/{user_id}/{uuid.uuid4()}/{safe_name}"
    if is_local_storage():
        path = _local_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(file.read())
    else:
        s3 = _get_s3_client()
        s3.upload_fileobj(file, settings.S3_BUCKET, key)
    return key


def upload_book_bytes(raw: bytes, user_id: str, filename: str) -> str:
    safe_name = Path(filename).name
    key = f"books/{user_id}/{uuid.uuid4()}/{safe_name}"
    if is_local_storage():
        path = _local_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    else:
        s3 = _get_s3_client()
        s3.put_object(
            Bucket=settings.S3_BUCKET,
            Key=key,
            Body=raw,
        )
    return key


def upload_binary(key: str, raw: bytes, content_type: str | None = None) -> str:
    if is_local_storage():
        path = _local_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    else:
        s3 = _get_s3_client()
        extra_args = {"Bucket": settings.S3_BUCKET, "Key": key, "Body": raw}
        if content_type:
            extra_args["ContentType"] = content_type
        s3.put_object(**extra_args)
    return key


def upload_text(key: str, content: str) -> str:
    if is_local_storage():
        path = _local_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    else:
        s3 = _get_s3_client()
        s3.put_object(
            Bucket=settings.S3_BUCKET,
            Key=key,
            Body=content.encode(),
            ContentType="text/plain",
        )
    return key


def download_book(key: str) -> bytes:
    if is_local_storage():
        return _local_path(key).read_bytes()
    s3 = _get_s3_client()
    return s3.get_object(Bucket=settings.S3_BUCKET, Key=key)["Body"].read()


def get_presigned_url(key: str, expires: int = 3600) -> str | None:
    if is_local_storage():
        return None
    s3 = _get_s3_client()
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.S3_BUCKET, "Key": key},
        ExpiresIn=expires,
    )
