import os
import shutil
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any, BinaryIO
from urllib.parse import urlparse

import boto3
from botocore.config import Config

from app.core.config import settings
from app.utils.observability_metrics import record_storage_operation

_S3_CLIENT: Any | None = None
_S3_CLIENT_CACHE_KEY: tuple[int, str | None, str | None, str | None, str] | None = None


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


def validate_storage_key(key: str) -> str:
    normalized = str(key or "").strip()
    if not normalized:
        raise ValueError("Storage key cannot be empty.")
    if "\x00" in normalized or "\\" in normalized or "//" in normalized:
        raise ValueError("Storage key contains invalid path separators.")
    key_path = Path(normalized)
    if key_path.is_absolute():
        raise ValueError("Storage key cannot be absolute.")
    parts = key_path.parts
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError("Storage key cannot contain traversal segments.")
    return "/".join(parts)


def _local_bucket_root() -> Path:
    return (_local_storage_root() / settings.S3_BUCKET).resolve()


def _local_path(key: str) -> Path:
    safe_key = validate_storage_key(key)
    root = _local_bucket_root()
    candidate = (root / safe_key).resolve()
    if root != candidate and root not in candidate.parents:
        raise ValueError("Storage key escapes the configured bucket.")
    return candidate


def _ensure_local_parent(path: Path) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        parent = path.parent
        storage_root = _local_storage_root().resolve()
        while parent != storage_root and not parent.exists():
            try:
                parent.mkdir(parents=True, exist_ok=True, mode=0o777)
            except PermissionError:
                parent = parent.parent
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o777)


def _write_local_bytes(key: str, raw: bytes) -> None:
    path = _local_path(key)
    _ensure_local_parent(path)
    path.write_bytes(raw)


def _write_local_text(key: str, content: str) -> None:
    path = _local_path(key)
    _ensure_local_parent(path)
    path.write_text(content, encoding="utf-8")


def _remaining_stream_size(file: BinaryIO) -> int:
    try:
        position = file.tell()
        file.seek(0, os.SEEK_END)
        end = file.tell()
        file.seek(position)
        return max(int(end - position), 0)
    except (AttributeError, OSError, ValueError):
        return 0


def _get_s3_client():
    global _S3_CLIENT, _S3_CLIENT_CACHE_KEY

    cache_key = (
        os.getpid(),
        settings.S3_ENDPOINT_URL,
        settings.AWS_ACCESS_KEY_ID,
        settings.AWS_SECRET_ACCESS_KEY,
        settings.S3_BUCKET,
    )
    if _S3_CLIENT is not None and _S3_CLIENT_CACHE_KEY == cache_key:
        return _S3_CLIENT

    _S3_CLIENT = boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT_URL,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        config=Config(
            signature_version="s3v4",
            connect_timeout=5,
            read_timeout=30,
            retries={"mode": "standard", "total_max_attempts": 4},
            tcp_keepalive=True,
        ),
    )
    _S3_CLIENT_CACHE_KEY = cache_key
    return _S3_CLIENT


def get_object_size(key: str) -> int:
    """Return the stored byte size without downloading a remote object."""
    key = validate_storage_key(key)
    if is_local_storage():
        size = _local_path(key).stat().st_size
    else:
        response = _get_s3_client().head_object(Bucket=settings.S3_BUCKET, Key=key)
        size = int(response["ContentLength"])
    record_storage_operation()
    return size


def _storage_owner_ids() -> tuple[int, int]:
    try:
        import pwd

        app_user = pwd.getpwnam("app")
        return app_user.pw_uid, app_user.pw_gid
    except (ImportError, KeyError, OSError):
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
    written = _remaining_stream_size(file)
    if is_local_storage():
        raw = file.read()
        _write_local_bytes(key, raw)
        written = len(raw)
    else:
        s3 = _get_s3_client()
        s3.upload_fileobj(file, settings.S3_BUCKET, key)
    record_storage_operation(bytes_written=written)
    return key


def upload_book_bytes(raw: bytes, user_id: str, filename: str) -> str:
    safe_name = Path(filename).name
    key = f"books/{user_id}/{uuid.uuid4()}/{safe_name}"
    if is_local_storage():
        _write_local_bytes(key, raw)
    else:
        s3 = _get_s3_client()
        s3.put_object(
            Bucket=settings.S3_BUCKET,
            Key=key,
            Body=raw,
        )
    record_storage_operation(bytes_written=len(raw))
    return key


def upload_binary(key: str, raw: bytes, content_type: str | None = None) -> str:
    key = validate_storage_key(key)
    if is_local_storage():
        _write_local_bytes(key, raw)
    else:
        s3 = _get_s3_client()
        extra_args = {"Bucket": settings.S3_BUCKET, "Key": key, "Body": raw}
        if content_type:
            extra_args["ContentType"] = content_type
        s3.put_object(**extra_args)
    record_storage_operation(bytes_written=len(raw))
    return key


def upload_fileobj(
    key: str,
    file: BinaryIO,
    content_type: str | None = None,
) -> str:
    """Upload a seekable stream without materializing it as another bytes object."""
    key = validate_storage_key(key)
    written = _remaining_stream_size(file)
    if is_local_storage():
        path = _local_path(key)
        _ensure_local_parent(path)
        with path.open("wb") as destination:
            shutil.copyfileobj(file, destination, length=1024 * 1024)
    else:
        s3 = _get_s3_client()
        extra_args = {"ContentType": content_type} if content_type else None
        if extra_args:
            s3.upload_fileobj(file, settings.S3_BUCKET, key, ExtraArgs=extra_args)
        else:
            s3.upload_fileobj(file, settings.S3_BUCKET, key)
    record_storage_operation(bytes_written=written)
    return key


def upload_text(key: str, content: str) -> str:
    key = validate_storage_key(key)
    raw = content.encode()
    if is_local_storage():
        _write_local_text(key, content)
    else:
        s3 = _get_s3_client()
        s3.put_object(
            Bucket=settings.S3_BUCKET,
            Key=key,
            Body=raw,
            ContentType="text/plain",
        )
    record_storage_operation(bytes_written=len(raw))
    return key


def upload_public_text_asset(key: str, content: str, *, cache_max_age: int = 60) -> str:
    """Write reader-safe public text under the only CDN-exposed storage prefix."""
    key = validate_storage_key(key)
    if not key.startswith("public-assets/"):
        raise ValueError("Public assets must use the public-assets/ storage prefix.")
    raw = content.encode()
    if is_local_storage():
        _write_local_text(key, content)
    else:
        _get_s3_client().put_object(
            Bucket=settings.S3_BUCKET,
            Key=key,
            Body=raw,
            ContentType="text/plain; charset=utf-8",
            CacheControl=f"public, max-age={max(0, min(int(cache_max_age), 3600))}, must-revalidate",
        )
    record_storage_operation(bytes_written=len(raw))
    return key


def download_book(key: str) -> bytes:
    key = validate_storage_key(key)
    if is_local_storage():
        raw = _local_path(key).read_bytes()
    else:
        s3 = _get_s3_client()
        raw = s3.get_object(Bucket=settings.S3_BUCKET, Key=key)["Body"].read()
    record_storage_operation(bytes_read=len(raw))
    return raw


def iter_object_chunks(key: str, *, chunk_size: int = 1024 * 1024) -> Iterator[bytes]:
    """Yield an object's bytes in bounded chunks for authenticated downloads."""
    key = validate_storage_key(key)
    bounded_chunk_size = max(64 * 1024, min(int(chunk_size), 8 * 1024 * 1024))
    if is_local_storage():
        with _local_path(key).open("rb") as source:
            while chunk := source.read(bounded_chunk_size):
                record_storage_operation(bytes_read=len(chunk))
                yield chunk
        return

    body = _get_s3_client().get_object(Bucket=settings.S3_BUCKET, Key=key)["Body"]
    try:
        for chunk in body.iter_chunks(chunk_size=bounded_chunk_size):
            if chunk:
                record_storage_operation(bytes_read=len(chunk))
                yield chunk
    finally:
        body.close()


def delete_object(key: str) -> None:
    key = validate_storage_key(key)
    if is_local_storage():
        path = _local_path(key)
        if path.exists():
            path.unlink()
    else:
        s3 = _get_s3_client()
        s3.delete_object(Bucket=settings.S3_BUCKET, Key=key)
    record_storage_operation()


def list_object_keys(prefix: str, *, limit: int = 1000) -> list[str]:
    """List at most ``limit`` validated object keys under a trusted prefix."""
    prefix = validate_storage_key(prefix).rstrip("/") + "/"
    bounded_limit = max(1, min(int(limit), 10_000))
    if is_local_storage():
        root = _local_path(prefix.rstrip("/"))
        if not root.exists():
            return []
        bucket_root = _local_bucket_root()
        keys = [
            path.relative_to(bucket_root).as_posix()
            for path in sorted(root.rglob("*"))
            if path.is_file()
        ][:bounded_limit]
        record_storage_operation()
        return keys

    s3 = _get_s3_client()
    keys: list[str] = []
    continuation_token: str | None = None
    while len(keys) < bounded_limit:
        request: dict[str, Any] = {
            "Bucket": settings.S3_BUCKET,
            "Prefix": prefix,
            "MaxKeys": min(1000, bounded_limit - len(keys)),
        }
        if continuation_token:
            request["ContinuationToken"] = continuation_token
        response = s3.list_objects_v2(**request)
        keys.extend(
            validate_storage_key(str(item["Key"]))
            for item in response.get("Contents", [])
            if item.get("Key")
        )
        if not response.get("IsTruncated"):
            break
        continuation_token = response.get("NextContinuationToken")
        if not continuation_token:
            break
    record_storage_operation()
    return keys[:bounded_limit]


def move_object(src_key: str, dst_key: str) -> str:
    """Move an object from src_key to dst_key, returning dst_key."""
    src_key = validate_storage_key(src_key)
    dst_key = validate_storage_key(dst_key)
    if src_key == dst_key:
        return dst_key
    if is_local_storage():
        src_path = _local_path(src_key)
        dst_path = _local_path(dst_key)
        if src_path.exists():
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            src_path.rename(dst_path)
    else:
        s3 = _get_s3_client()
        s3.copy_object(
            Bucket=settings.S3_BUCKET,
            CopySource={"Bucket": settings.S3_BUCKET, "Key": src_key},
            Key=dst_key,
        )
        s3.delete_object(Bucket=settings.S3_BUCKET, Key=src_key)
    record_storage_operation()
    return dst_key


def get_presigned_url(key: str, expires: int = 3600) -> str | None:
    key = validate_storage_key(key)
    if is_local_storage():
        return None
    s3 = _get_s3_client()
    url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.S3_BUCKET, "Key": key},
        ExpiresIn=expires,
    )
    record_storage_operation()
    return url
