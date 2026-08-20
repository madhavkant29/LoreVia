from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.utils.books.revision_milestones import create_revision_round


@pytest.mark.asyncio
async def test_revision_round_rejects_blank_labels_before_snapshotting():
    with pytest.raises(HTTPException) as exc_info:
        await create_revision_round(
            None,
            book=SimpleNamespace(),
            label="   ",
            note=None,
        )

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_revision_round_rejects_empty_projects():
    class EmptyResult:
        def scalars(self):
            return self

        def all(self):
            return []

    class EmptyDb:
        async def execute(self, statement):
            return EmptyResult()

    with pytest.raises(HTTPException) as exc_info:
        await create_revision_round(
            EmptyDb(),
            book=SimpleNamespace(id="book-1"),
            label="Structural pass",
            note=None,
        )

    assert exc_info.value.status_code == 409
