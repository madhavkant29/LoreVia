import uuid

import pytest
from sqlalchemy import select

from app.models.book import Book, Chapter
from app.models.character import Character
from app.models.intelligence import PlotThread
from app.models.user import User
from app.utils.ingestion_utils import ANALYSIS_INFLIGHT_TTL_SECONDS
from app.workers.consumers.analysis_consumer import _upsert_plot_threads


def test_inflight_lock_ttl_exceeds_hard_limit():
    ANALYSIS_HARD_LIMIT = 15 * 60        # celery_app.py task_annotations time_limit
    MINIMUM_TTL = ANALYSIS_HARD_LIMIT + 300
    assert ANALYSIS_INFLIGHT_TTL_SECONDS >= MINIMUM_TTL


@pytest.mark.asyncio
async def test_upsert_plot_threads_resolves_related_characters_to_canonical_names(db):
    user = User(email="plot-analysis@lorevia.app", username="plotanalysis", password_hash="hash")
    db.add(user)
    await db.flush()

    book = Book(user_id=user.id, title="Plot Analysis", format="pdf", s3_key="plot-analysis.pdf", status="ready")
    db.add(book)
    await db.flush()

    chapter = Chapter(id=uuid.uuid4(), book_id=book.id, number=4, title="Door", s3_key="chapter-4.txt")
    grete = Character(book_id=book.id, name="Grete", aliases=[], first_chapter=1, mention_count=3)
    gregor = Character(book_id=book.id, name="Gregor", aliases=[], first_chapter=1, mention_count=3)
    db.add_all([chapter, grete, gregor])
    await db.commit()

    await _upsert_plot_threads(
        db,
        book,
        chapter,
        [
            {
                "title": "The door plea",
                "description": "Grete, Gregor's sister, begs him to answer.",
                "status": "developing",
                "characters_involved": ["Gregor's sister", "Gregor"],
                "importance": 7,
            }
        ],
    )
    await db.commit()

    thread = (await db.execute(select(PlotThread).where(PlotThread.book_id == book.id))).scalar_one()

    assert thread.character_ids == ["Grete", "Gregor"]
