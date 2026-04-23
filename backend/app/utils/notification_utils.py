"""
Notification utility helpers for building and storing in-app notifications.
"""
from __future__ import annotations

from app.models.book import Book
from app.models.intelligence import Notification
from app.schemas.books import ChapterConsistencyReport


def build_chapter_report_notification(
    book: Book,
    report: ChapterConsistencyReport,
) -> Notification | None:
    noteworthy_count = (
        len(report.new_characters)
        + len(report.relationship_changes)
        + len(report.plot_threads_opened)
        + len(report.continuity_flags)
    )
    if noteworthy_count == 0:
        return None

    if report.new_characters:
        names = ", ".join(character.name for character in report.new_characters[:4])
        extra = len(report.new_characters) - 4
        if extra > 0:
            names = f"{names}, and {extra} more"
        title = f"{len(report.new_characters)} new character{'s' if len(report.new_characters) != 1 else ''} detected in Chapter {report.chapter_number}"
        body = f"{names}. Review their extracted profiles and the latest chapter report."
    else:
        title = f"Chapter {report.chapter_number} consistency report ready"
        body = report.summary

    return Notification(
        user_id=book.user_id,
        book_id=book.id,
        kind="chapter_report",
        title=title,
        body=body,
        data={
            "chapter_number": report.chapter_number,
            "chapter_title": report.chapter_title,
            "book_title": book.title,
            "summary": report.summary,
            "new_characters": [character.model_dump() for character in report.new_characters],
            "relationship_changes": report.relationship_changes,
            "plot_threads_opened": report.plot_threads_opened,
            "plot_threads_resolved": report.plot_threads_resolved,
            "continuity_flags": report.continuity_flags,
        },
    )


def build_continuity_risk_notifications(
    book: Book,
    report: ChapterConsistencyReport,
) -> list[Notification]:
    notifications: list[Notification] = []
    for flag in report.continuity_flags[:2]:
        notifications.append(
            Notification(
                user_id=book.user_id,
                book_id=book.id,
                kind="continuity_risk",
                title="Readers might notice an inconsistency",
                body=flag,
                data={
                    "chapter_number": report.chapter_number,
                    "chapter_title": report.chapter_title,
                    "book_title": book.title,
                    "summary": report.summary,
                },
            )
        )
    return notifications
