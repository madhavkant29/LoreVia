"""Regression tests for duplicate-upload protection (content fingerprinting)."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import Book
from app.models.user import User
from app.services.book_upload_service import (
    find_active_duplicate_upload,
    upload_source_fingerprint,
)


async def _create_user(db: AsyncSession) -> User:
    user = User(
        email=f"dup-{uuid.uuid4().hex[:8]}@lorevia.app",
        username=f"dup{uuid.uuid4().hex[:8]}",
        password_hash="fake",
        tier="author",
    )
    db.add(user)
    await db.flush()
    return user


async def _create_book(
    db: AsyncSession,
    *,
    user: User,
    fingerprint: str,
    status: str = "pending",
) -> Book:
    book = Book(
        user_id=user.id,
        title="Duplicate Candidate",
        format="txt",
        work_type="novel",
        s3_key=f"books/{user.id}/{uuid.uuid4()}/manuscript.txt",
        status=status,
        mode="author",
        writer_workspace={"source_fingerprint": fingerprint},
    )
    db.add(book)
    await db.flush()
    return book


def test_fingerprint_is_deterministic_sha256():
    first = upload_source_fingerprint(b"chapter one")
    second = upload_source_fingerprint(b"chapter one")
    third = upload_source_fingerprint(b"chapter two")
    assert first == second
    assert first != third
    assert len(first) == 64


@pytest.mark.asyncio
async def test_duplicate_detection_is_scoped_to_user_and_active_status(db: AsyncSession):
    fingerprint = upload_source_fingerprint(b"same manuscript bytes")
    user_a = await _create_user(db)
    user_b = await _create_user(db)
    active_book = await _create_book(db, user=user_a, fingerprint=fingerprint, status="processing")
    await _create_book(db, user=user_b, fingerprint=fingerprint, status="processing")
    await db.commit()

    found_for_owner = await find_active_duplicate_upload(
        db, user_id=user_a.id, fingerprint=fingerprint
    )
    found_for_other = await find_active_duplicate_upload(
        db, user_id=user_b.id, fingerprint=upload_source_fingerprint(b"different bytes")
    )
    assert found_for_owner is not None
    assert found_for_owner.id == active_book.id
    assert found_for_other is None


@pytest.mark.asyncio
async def test_failed_and_ready_books_do_not_block_reupload(db: AsyncSession):
    fingerprint = upload_source_fingerprint(b"revised draft")
    user = await _create_user(db)
    await _create_book(db, user=user, fingerprint=fingerprint, status="failed")
    await db.commit()
    assert (
        await find_active_duplicate_upload(db, user_id=user.id, fingerprint=fingerprint)
    ) is None

    user_two = await _create_user(db)
    await _create_book(db, user=user_two, fingerprint=fingerprint, status="ready")
    await db.commit()
    assert (
        await find_active_duplicate_upload(db, user_id=user_two.id, fingerprint=fingerprint)
    ) is None


@pytest.mark.asyncio
async def test_missing_fingerprint_never_matches(db: AsyncSession):
    user = await _create_user(db)
    await _create_book(db, user=user, fingerprint="")
    await db.commit()
    assert await find_active_duplicate_upload(db, user_id=user.id, fingerprint="") is None
