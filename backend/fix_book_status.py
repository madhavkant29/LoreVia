"""
Script to check and fix book status for books that have completed processing.
"""
import asyncio
from app.core.database import AsyncSessionLocal
from app.models.book import Book
from app.models.chapter import Chapter
from app.utils.notification_utils import collect_book_ready_stats
from sqlalchemy import select, func


async def fix_book_status():
    async with AsyncSessionLocal() as db:
        # Find books with status "processing"
        books = (
            await db.execute(
                select(Book)
                .where(Book.status == "processing")
                .order_by(Book.created_at.desc())
                .limit(20)
            )
        ).scalars().all()
        
        print(f"Found {len(books)} books with status 'processing'")
        print()
        
        for book in books:
            # Check if all chapters are processed
            total_chapters = (
                await db.execute(
                    select(func.count())
                    .select_from(Chapter)
                    .where(Chapter.book_id == book.id)
                )
            ).scalar_one()
            
            processed_chapters = (
                await db.execute(
                    select(func.count())
                    .select_from(Chapter)
                    .where(Chapter.book_id == book.id, Chapter.processed == True)
                )
            ).scalar_one()
            
            print(f"Book: {book.title}")
            print(f"  ID: {book.id}")
            print(f"  Status: {book.status}")
            print(f"  Chapters: {processed_chapters}/{total_chapters} processed")
            
            # If all chapters are processed, check if analysis is complete
            if total_chapters > 0 and processed_chapters >= total_chapters:
                stats = await collect_book_ready_stats(db, book)
                print(f"  Analysis: {stats.analyzed_chapter_count}/{stats.chapter_count} complete")
                print(f"  Analysis complete: {stats.analysis_complete}")
                
                # If analysis is complete, update status to ready
                if stats.analysis_complete:
                    print(f"  -> Updating status to 'ready'")
                    book.status = "ready"
                    await db.commit()
                else:
                    print(f"  -> Keeping status as 'processing' (analysis not complete)")
            else:
                print(f"  -> Keeping status as 'processing' (extraction not complete)")
            
            print()


if __name__ == "__main__":
    asyncio.run(fix_book_status())
