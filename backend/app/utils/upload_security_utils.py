from __future__ import annotations

import io
import zipfile

from fastapi import HTTPException, UploadFile

from app.core.config import settings

_COVER_MAGIC: dict[bytes, tuple[str, str]] = {
    b"\xff\xd8\xff": ("jpg", "image/jpeg"),
    b"\x89PNG": ("png", "image/png"),
    b"GIF8": ("gif", "image/gif"),
    b"RIFF": ("webp", "image/webp"),
}
_OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


async def read_upload_bounded(upload: UploadFile, max_bytes: int, label: str) -> bytes:
    """Read an UploadFile in chunks, raising 413 if the size cap is exceeded."""
    parts: list[bytes] = []
    total = 0

    while True:
        chunk = await upload.read(1024 * 1024)
        if not chunk:
            break

        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                413,
                f"{label} exceeds the maximum allowed size ({max_bytes // 1024 // 1024} MB).",
            )
        parts.append(chunk)

    await upload.seek(0)
    return b"".join(parts)


def validate_cover_magic(raw: bytes) -> tuple[str, str]:
    """Return (extension, mime_type) after validating image magic bytes."""
    for magic, (suffix, mime) in _COVER_MAGIC.items():
        if raw[: len(magic)] == magic:
            if mime == "image/webp" and raw[8:12] != b"WEBP":
                continue
            return suffix, mime
    raise HTTPException(400, "Cover image must be a JPEG, PNG, GIF, or WebP file.")


def validate_document_upload_bytes(filename: str, raw: bytes, format_name: str) -> None:
    """Perform lightweight server-side content validation for supported uploads."""
    if not raw:
        raise HTTPException(400, f"{filename} is empty.")

    if format_name == "pdf":
        _validate_pdf_bytes(filename, raw)
        return
    if format_name == "epub":
        validate_zip_archive_safety(
            raw,
            max_entries=settings.UPLOAD_ARCHIVE_MAX_ENTRIES,
            max_total_uncompressed_bytes=settings.UPLOAD_ARCHIVE_MAX_UNCOMPRESSED_BYTES,
            max_compression_ratio=settings.UPLOAD_ARCHIVE_MAX_COMPRESSION_RATIO,
            label=filename,
        )
        _validate_zip_container(
            filename,
            raw,
            required_names={"mimetype"},
            required_exact={"mimetype": b"application/epub+zip"},
        )
        return
    if format_name == "docx":
        validate_zip_archive_safety(
            raw,
            max_entries=settings.UPLOAD_ARCHIVE_MAX_ENTRIES,
            max_total_uncompressed_bytes=settings.UPLOAD_ARCHIVE_MAX_UNCOMPRESSED_BYTES,
            max_compression_ratio=settings.UPLOAD_ARCHIVE_MAX_COMPRESSION_RATIO,
            label=filename,
        )
        _validate_zip_container(filename, raw, required_names={"word/document.xml"})
        return
    if format_name == "doc":
        if not raw.startswith(_OLE_MAGIC):
            raise HTTPException(400, f"{filename} is not a valid DOC file.")
        return
    if format_name in {"txt", "md", "fountain"}:
        _validate_text_upload(filename, raw)
        return

    raise HTTPException(400, f"Unsupported upload format: {filename}")


def validate_zip_archive_safety(
    archive_bytes: bytes,
    *,
    max_entries: int,
    max_total_uncompressed_bytes: int,
    max_compression_ratio: int,
    label: str,
) -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            members = [item for item in archive.infolist() if not item.is_dir()]
            if len(members) > max_entries:
                raise HTTPException(400, f"{label} contains too many files.")

            total_uncompressed = 0
            for member in members:
                if _zip_member_is_suspicious(member, max_compression_ratio):
                    raise HTTPException(
                        400, f"{label} appears to contain an unsafe compressed file."
                    )
                total_uncompressed += int(member.file_size or 0)
                if total_uncompressed > max_total_uncompressed_bytes:
                    raise HTTPException(400, f"{label} expands beyond the maximum allowed size.")
    except zipfile.BadZipFile as exc:
        raise HTTPException(400, f"Invalid {label}") from exc


def _validate_pdf_bytes(filename: str, raw: bytes) -> None:
    if not raw.startswith(b"%PDF-"):
        raise HTTPException(400, f"{filename} is not a valid PDF file.")
    if len(raw) < 8:
        raise HTTPException(400, f"{filename} appears to be an incomplete PDF file.")


def _validate_text_upload(filename: str, raw: bytes) -> None:
    if b"\x00" in raw:
        raise HTTPException(400, f"{filename} must be a text-based file.")
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(400, f"{filename} must be UTF-8 encoded.") from exc


def _validate_zip_container(
    filename: str,
    raw: bytes,
    *,
    required_names: set[str],
    required_exact: dict[str, bytes] | None = None,
) -> None:
    required_exact = required_exact or {}
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            names = set(archive.namelist())
            missing = required_names - names
            if missing:
                raise HTTPException(400, f"{filename} is missing required internal files.")
            for member_name, expected_value in required_exact.items():
                if archive.read(member_name) != expected_value:
                    raise HTTPException(400, f"{filename} is not a valid {member_name} container.")
    except zipfile.BadZipFile as exc:
        raise HTTPException(400, f"{filename} is not a valid ZIP-based document.") from exc


def _zip_member_is_suspicious(member: zipfile.ZipInfo, max_compression_ratio: int) -> bool:
    compressed_size = int(member.compress_size or 0)
    uncompressed_size = int(member.file_size or 0)

    if uncompressed_size < 0 or compressed_size < 0:
        return True
    if compressed_size == 0:
        return uncompressed_size > 0
    return (uncompressed_size / compressed_size) > max_compression_ratio
