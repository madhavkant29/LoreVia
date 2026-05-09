import uuid
import os
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
        if parsed.netloc:
            path = f"{parsed.netloc}{parsed.path}"
        else:
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


def _storage_owner_ids() -> tuple[int, int]:
    try:
        import pwd

        app_user = pwd.getpwnam("app")
        return app_user.pw_uid, app_user.pw_gid
    except Exception:
        # The API container does not create the `app` user, but the worker
        # image runs Celery as uid/gid 10001. Use that service account as the
        # portable fallback so shared local volumes end up writable by workers.
        return 10001, 10001


def _apply_local_storage_permissions(path: Path, uid: int, gid: int) -> None:
    try:
        os.chown(path, uid, gid)
    except (AttributeError, FileNotFoundError, PermissionError, OSError):
        pass

    try:
        os.chmod(path, 0o775 if path.is_dir() else 0o664)
    except (AttributeError, FileNotFoundError, PermissionError, OSError):
        pass


def ensure_local_storage_permissions() -> None:
    if not is_local_storage():
        return
    if not hasattr(os, "geteuid") or os.geteuid() != 0:
        return

    storage_root = _local_storage_root()
    storage_root.mkdir(parents=True, exist_ok=True)

    uid, gid = _storage_owner_ids()
    for current_root, dirnames, filenames in os.walk(storage_root):
        current_path = Path(current_root)
        _apply_local_storage_permissions(current_path, uid, gid)
        for dirname in dirnames:
            _apply_local_storage_permissions(current_path / dirname, uid, gid)
        for filename in filenames:
            _apply_local_storage_permissions(current_path / filename, uid, gid)


def upload_book(file: BinaryIO, user_id: str, filename: str) -> str:
    safe_name = Path(filename).name
    key = f"books/{user_id}/{uuid.uuid4()}/{safe_name}"
    if is_local_storage():
        path = _local_path(key)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            # Fallback: create directories with 777 permissions if initial mkdir fails
            import os
            parent = path.parent
            while parent != _local_storage_root() and not parent.exists():
                try:
                    parent.mkdir(parents=True, exist_ok=True, mode=0o777)
                except PermissionError:
                    parent = parent.parent
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o777)
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
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            import os
            parent = path.parent
            while parent != _local_storage_root() and not parent.exists():
                try:
                    parent.mkdir(parents=True, exist_ok=True, mode=0o777)
                except PermissionError:
                    parent = parent.parent
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o777)
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
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            import os
            parent = path.parent
            while parent != _local_storage_root() and not parent.exists():
                try:
                    parent.mkdir(parents=True, exist_ok=True, mode=0o777)
                except PermissionError:
                    parent = parent.parent
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o777)
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
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            import os
            parent = path.parent
            while parent != _local_storage_root() and not parent.exists():
                try:
                    parent.mkdir(parents=True, exist_ok=True, mode=0o777)
                except PermissionError:
                    parent = parent.parent
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o777)
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
