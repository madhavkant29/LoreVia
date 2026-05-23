from __future__ import annotations

from app.workers.tasks.analysis_tasks import analyse_chapter_task
from app.workers.tasks.embedding_tasks import update_character_embedding_task
from app.workers.tasks.extraction_tasks import (
    process_book_task,
    process_chapter_task,
    repair_chapter_payload_task,
)
from app.workers.tasks.intelligence_tasks import (
    generate_advisor_reply_task,
    generate_series_advisor_reply_task,
    generate_wiki_task,
)
from app.workers.tasks.maintenance_tasks import (
    cleanup_expired_advisor_jobs_task,
    process_beta_reads_task,
    send_due_trial_emails_task,
)


def test_background_tasks_ignore_results_to_reduce_redis_pressure():
    assert process_book_task.ignore_result is True
    assert process_chapter_task.ignore_result is True
    assert repair_chapter_payload_task.ignore_result is True
    assert analyse_chapter_task.ignore_result is True
    assert update_character_embedding_task.ignore_result is True
    assert generate_wiki_task.ignore_result is True
    assert send_due_trial_emails_task.ignore_result is True
    assert process_beta_reads_task.ignore_result is True
    assert cleanup_expired_advisor_jobs_task.ignore_result is True


def test_advisor_tasks_ignore_results_after_database_polling_migration():
    assert generate_advisor_reply_task.ignore_result is True
    assert generate_series_advisor_reply_task.ignore_result is True
