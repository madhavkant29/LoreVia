import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user, get_optional_current_user
from app.core.database import get_db
from app.core.redis import (
    cache_del,
    cache_get,
    cache_set,
    key_public_book_detail,
    key_public_books,
    key_public_chapter,
)
from app.core.storage import download_book, get_presigned_url, upload_text
from app.models.book import Book, Chapter
from app.models.user import User
from app.parsers.chunker import count_tokens
from app.schemas.public import (
    PublicBookCreateOut,
    PublicBookDetailOut,
    PublicBookManualIn,
    PublicBookOut,
    PublicChapterAppendOut,
    PublicChapterOut,
    PublicChapterIn,
    PublicForumInterestCreateBody,
    PublicForumInterestListOut,
    PublicForumInterestOut,
    PublicForumCommentCreateBody,
    PublicForumCommentListOut,
    PublicForumCommentOut,
    PublicForumCommentReactionBody,
    PublicForumPostCreateBody,
    PublicForumPostListOut,
    PublicForumPostOut,
    PublicForumPostUpdateBody,
    PublicUserProfileOut,
)
from app.utils.book_utils import deserialize_manuscript_content
from app.utils.public_utils import (
    create_public_forum_interest,
    create_public_forum_comment,
    create_public_forum_post,
    ensure_public_mode_enabled,
    get_public_forum_post_detail,
    get_public_user_profile,
    list_public_forum_interests_for_author,
    list_public_forum_comments,
    list_public_forum_posts,
    react_to_public_forum_comment,
    update_public_forum_post,
)
from app.services.monetization_service import charge_public_share_points

router = APIRouter()


@router.get("/forum/posts", response_model=PublicForumPostListOut)
async def list_public_beta_forum_posts(
    q: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    ensure_public_mode_enabled()
    return PublicForumPostListOut(items=await list_public_forum_posts(db, q=q))


@router.get("/forum/posts/{post_id}", response_model=PublicForumPostOut)
async def get_public_beta_forum_post(
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    ensure_public_mode_enabled()
    return await get_public_forum_post_detail(db, post_id=post_id)


@router.post("/forum/posts", response_model=PublicForumPostOut, status_code=201)
async def create_public_beta_forum_post_endpoint(
    body: PublicForumPostCreateBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    ensure_public_mode_enabled()
    return await create_public_forum_post(db, current_user=current_user, body=body)


@router.put("/forum/posts/{post_id}", response_model=PublicForumPostOut)
async def edit_public_beta_forum_post_endpoint(
    post_id: uuid.UUID,
    body: PublicForumPostUpdateBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    ensure_public_mode_enabled()
    return await update_public_forum_post(db, post_id=post_id, current_user=current_user, body=body)


@router.post("/forum/posts/{post_id}/interests", response_model=PublicForumInterestOut, status_code=201)
async def create_public_beta_forum_interest_endpoint(
    post_id: uuid.UUID,
    body: PublicForumInterestCreateBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    ensure_public_mode_enabled()
    return await create_public_forum_interest(db, post_id=post_id, current_user=current_user, body=body)


@router.get("/forum/posts/{post_id}/interests", response_model=PublicForumInterestListOut)
async def list_public_beta_forum_interests(
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    ensure_public_mode_enabled()
    return PublicForumInterestListOut(
        items=await list_public_forum_interests_for_author(
            db,
            post_id=post_id,
            author_user_id=current_user.id,
        )
    )


@router.get("/forum/posts/{post_id}/comments", response_model=PublicForumCommentListOut)
async def list_public_beta_forum_comments(
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_optional_current_user),
):
    ensure_public_mode_enabled()
    return PublicForumCommentListOut(
        items=await list_public_forum_comments(
            db,
            post_id=post_id,
            current_user=current_user,
        )
    )


@router.post("/forum/posts/{post_id}/comments", response_model=PublicForumCommentOut, status_code=201)
async def create_public_beta_forum_comment(
    post_id: uuid.UUID,
    body: PublicForumCommentCreateBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    ensure_public_mode_enabled()
    return await create_public_forum_comment(db, post_id=post_id, current_user=current_user, body=body)


@router.put("/forum/comments/{comment_id}/reaction", response_model=PublicForumCommentOut)
async def react_to_public_beta_forum_comment(
    comment_id: uuid.UUID,
    body: PublicForumCommentReactionBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    ensure_public_mode_enabled()
    return await react_to_public_forum_comment(
        db,
        comment_id=comment_id,
        current_user=current_user,
        reaction=body.reaction,
    )


@router.get("/users/{username}", response_model=PublicUserProfileOut)
async def get_public_user_profile_endpoint(
    username: str,
    db: AsyncSession = Depends(get_db),
):
    ensure_public_mode_enabled()
    return await get_public_user_profile(db, username=username)


@router.get("/books", response_model=list[PublicBookOut])
async def list_public_books(db: AsyncSession = Depends(get_db)):
    ensure_public_mode_enabled()
    cached = await cache_get(key_public_books())
    if cached:
        return cached

    rows = (await db.execute(
        select(Book, User.username)
        .join(User, User.id == Book.user_id)
        .where(
            Book.is_public.is_(True),
            Book.hidden_at.is_(None),
            Book.archived_at.is_(None),
            Book.status.in_(["ready", "processing", "pending"]),
        )
        .order_by(Book.created_at.desc())
    )).all()
    payload = [
        {
            "id": str(book.id),
            "title": book.title,
            "author": book.author,
            "author_username": username,
            "genre": book.genre,
            "description": book.public_description,
            "format": book.format,
            "work_type": book.work_type,
            "status": book.status,
            "total_chapters": book.total_chapters,
            "copyright_warning": book.copyright_warning,
            "created_at": book.created_at,
        }
        for book, username in rows
    ]
    await cache_set(key_public_books(), payload, 300)
    return payload


@router.get("/books/{book_id}", response_model=PublicBookDetailOut)
async def get_public_book(book_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    ensure_public_mode_enabled()
    cached = await cache_get(key_public_book_detail(str(book_id)))
    if cached:
        return cached

    book = await db.get(Book, book_id)
    if not book or not book.is_public or book.hidden_at is not None or book.archived_at is not None:
        raise HTTPException(404, "Public book not found")
    author_user = await db.get(User, book.user_id)

    chapters = (await db.execute(
        select(Chapter.number, Chapter.title, Chapter.description)
        .where(Chapter.book_id == book.id)
        .order_by(Chapter.number)
    )).all()

    payload = {
        "id": str(book.id),
        "title": book.title,
        "author": book.author,
        "author_username": author_user.username if author_user else None,
        "genre": book.genre,
        "description": book.public_description,
        "format": book.format,
        "work_type": book.work_type,
        "status": book.status,
        "total_chapters": book.total_chapters,
        "copyright_warning": book.copyright_warning,
        "chapters": [
            {"number": number, "title": title, "description": description}
            for number, title, description in chapters
        ],
    }
    await cache_set(key_public_book_detail(str(book_id)), payload, 300)
    return payload


@router.get("/books/{book_id}/chapter/{chapter_num}", response_model=PublicChapterOut)
async def get_public_chapter(book_id: uuid.UUID, chapter_num: int, db: AsyncSession = Depends(get_db)):
    ensure_public_mode_enabled()
    cached = await cache_get(key_public_chapter(str(book_id), chapter_num))
    if cached:
        return cached

    book = await db.get(Book, book_id)
    if not book or not book.is_public or book.hidden_at is not None or book.archived_at is not None:
        raise HTTPException(404, "Public book not found")

    chapter = (await db.execute(
        select(Chapter).where(Chapter.book_id == book.id, Chapter.number == chapter_num)
    )).scalar()
    if not chapter:
        raise HTTPException(404, "Chapter not found")

    stored_payload = deserialize_manuscript_content(download_book(chapter.s3_key)) if chapter.s3_key else {"text": None, "html": None}
    payload = {
        "book_id": str(book.id),
        "book_title": book.title,
        "chapter_number": chapter.number,
        "chapter_title": chapter.title,
        "chapter_description": chapter.description,
        "total_chapters": book.total_chapters,
        "text_url": get_presigned_url(chapter.s3_key) if chapter.s3_key else None,
        "text_content": stored_payload.get("text"),
        "html_content": stored_payload.get("html"),
    }
    await cache_set(key_public_chapter(str(book_id), chapter_num), payload, 3600)
    return payload


@router.post("/books/manual", response_model=PublicBookCreateOut)
async def create_public_book_manual(
    body: PublicBookManualIn,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    ensure_public_mode_enabled()
    if not body.chapters:
        raise HTTPException(400, "At least one chapter is required")
    book_id = uuid.uuid4()
    try:
        await charge_public_share_points(
            db,
            current_user,
            source_id=str(book_id),
            metadata={
                "book_title": body.title,
                "visibility": "public",
                "entrypoint": "manual_public_book",
            },
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    book = Book(
        id=book_id,
        user_id=current_user.id,
        title=body.title,
        author=body.author,
        genre=body.genre,
        format="manual",
        s3_key=f"public/manual/{current_user.id}/{body.title}".replace(" ", "-").lower(),
        status="ready",
        is_public=True,
        public_description=body.description,
    )
    db.add(book)
    await db.flush()

    total_tokens = 0
    for index, chapter_in in enumerate(body.chapters, start=1):
        chapter_key = f"public_chapters/{book.id}/{index}.txt"
        upload_text(chapter_key, chapter_in.text)
        total_tokens += count_tokens(chapter_in.text)
        db.add(
            Chapter(
                book_id=book.id,
                number=index,
                title=chapter_in.title,
                description=chapter_in.description,
                s3_key=chapter_key,
                token_count=count_tokens(chapter_in.text),
                processed=False,
            )
        )

    book.total_chapters = len(body.chapters)
    book.total_tokens = total_tokens
    await db.commit()
    await db.refresh(book)
    await cache_del(key_public_books())
    return {"book_id": str(book.id), "status": "ready", "visibility": "public"}


@router.post("/books/{book_id}/chapters", response_model=PublicChapterAppendOut)
async def append_public_chapter(
    book_id: uuid.UUID,
    body: PublicChapterIn,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    ensure_public_mode_enabled()
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id or not book.is_public:
        raise HTTPException(404, "Public book not found")

    next_number = (await db.execute(
        select(func.coalesce(func.max(Chapter.number), 0) + 1).where(Chapter.book_id == book.id)
    )).scalar_one()
    chapter_key = f"public_chapters/{book.id}/{next_number}.txt"
    upload_text(chapter_key, body.text)
    token_count = count_tokens(body.text)
    db.add(
        Chapter(
            book_id=book.id,
            number=next_number,
            title=body.title,
            description=body.description,
            s3_key=chapter_key,
            token_count=token_count,
            processed=False,
        )
    )
    book.total_chapters = next_number
    book.total_tokens = (book.total_tokens or 0) + token_count
    await db.commit()
    await cache_del(key_public_book_detail(str(book.id)))
    await cache_del(key_public_chapter(str(book.id), next_number))
    await cache_del(key_public_books())
    return {"book_id": str(book.id), "chapter_number": next_number, "saved": True}
