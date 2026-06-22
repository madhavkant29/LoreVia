import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.core.database import get_db
from app.schemas.beta_reads import (
    BetaReadAssignmentCreateBody,
    BetaReadAssignmentDetailOut,
    BetaReadAssignmentListOut,
    BetaReadAssignmentOut,
    BetaReadFeedbackItemAuthorUpdateBody,
    BetaReadFeedbackItemCreateBody,
    BetaReadFeedbackSubmitBody,
    BetaReadQuestionAppendBody,
    BetaReadQuestionOut,
    BetaReadSyncOut,
)
from app.utils.beta_read_utils import (
    add_beta_read_feedback_item,
    append_beta_read_questions,
    award_submitted_beta_reads,
    build_beta_read_assignment_detail_out,
    build_beta_read_assignment_out,
    create_beta_read_assignment,
    delete_beta_read_feedback_item,
    get_beta_assignment_for_author,
    get_beta_assignment_for_reader,
    list_book_beta_read_assignments,
    list_reader_beta_read_assignments,
    revoke_beta_read_assignment,
    start_beta_read,
    submit_beta_read_feedback,
    sync_beta_assignment_progress,
    update_beta_read_feedback_item_author_state,
)
from app.utils.billing_utils import require_author_access
from app.utils.books.notes import (
    get_owned_book,
)

router = APIRouter()


@router.post("/books/{book_id}/beta-reads", response_model=BetaReadAssignmentOut, status_code=201)
async def create_book_beta_read_assignment(
    book_id: uuid.UUID,
    body: BetaReadAssignmentCreateBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    assignment = await create_beta_read_assignment(
        db, book=book, current_user=current_user, body=body
    )
    return await build_beta_read_assignment_out(db, assignment=assignment)


@router.get("/books/{book_id}/beta-reads", response_model=BetaReadAssignmentListOut)
async def list_book_beta_reads(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    return BetaReadAssignmentListOut(
        items=await list_book_beta_read_assignments(db, book=book, author_user_id=current_user.id)
    )


@router.get(
    "/books/{book_id}/beta-reads/{assignment_id}", response_model=BetaReadAssignmentDetailOut
)
async def get_book_beta_read_detail(
    book_id: uuid.UUID,
    assignment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    assignment = await get_beta_assignment_for_author(
        db, assignment_id=assignment_id, author_user_id=current_user.id
    )
    if assignment.book_id != book.id:
        raise HTTPException(404, "Beta read assignment not found.")
    return await build_beta_read_assignment_detail_out(db, assignment=assignment)


@router.post(
    "/books/{book_id}/beta-reads/{assignment_id}/questions",
    response_model=list[BetaReadQuestionOut],
)
async def append_book_beta_read_questions(
    book_id: uuid.UUID,
    assignment_id: uuid.UUID,
    body: BetaReadQuestionAppendBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    assignment = await get_beta_assignment_for_author(
        db, assignment_id=assignment_id, author_user_id=current_user.id
    )
    if assignment.book_id != book.id:
        raise HTTPException(404, "Beta read assignment not found.")
    await append_beta_read_questions(db, assignment=assignment, questions=body.questions)
    detail = await build_beta_read_assignment_detail_out(db, assignment=assignment)
    return detail.author_questions


@router.post(
    "/books/{book_id}/beta-reads/{assignment_id}/revoke", response_model=BetaReadAssignmentOut
)
async def revoke_book_beta_read_assignment(
    book_id: uuid.UUID,
    assignment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    assignment = await get_beta_assignment_for_author(
        db, assignment_id=assignment_id, author_user_id=current_user.id
    )
    if assignment.book_id != book.id:
        raise HTTPException(404, "Beta read assignment not found.")
    revoked = await revoke_beta_read_assignment(db, assignment=assignment)
    return await build_beta_read_assignment_out(db, assignment=revoked)


@router.get("/beta-reads/upcoming", response_model=BetaReadAssignmentListOut)
async def list_upcoming_beta_reads(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return BetaReadAssignmentListOut(
        items=await list_reader_beta_read_assignments(
            db, current_user=current_user, upcoming_only=True
        )
    )


@router.get("/beta-reads", response_model=BetaReadAssignmentListOut)
async def list_reader_beta_reads(
    bucket: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return BetaReadAssignmentListOut(
        items=await list_reader_beta_read_assignments(db, current_user=current_user, bucket=bucket)
    )


@router.get("/beta-reads/{assignment_id}", response_model=BetaReadAssignmentDetailOut)
async def get_reader_beta_read_detail(
    assignment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    assignment = await get_beta_assignment_for_reader(
        db, assignment_id=assignment_id, current_user=current_user
    )
    return await build_beta_read_assignment_detail_out(
        db, assignment=assignment, current_user=current_user
    )


@router.post("/beta-reads/{assignment_id}/start", response_model=BetaReadAssignmentOut)
async def begin_beta_read(
    assignment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    assignment = await get_beta_assignment_for_reader(
        db, assignment_id=assignment_id, current_user=current_user
    )
    assignment = await start_beta_read(db, assignment=assignment, current_user=current_user)
    return await build_beta_read_assignment_out(
        db, assignment=assignment, current_user=current_user
    )


@router.post("/beta-reads/{assignment_id}/sync", response_model=BetaReadSyncOut)
async def sync_beta_read_assignment_progress(
    assignment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    assignment = await get_beta_assignment_for_reader(
        db, assignment_id=assignment_id, current_user=current_user
    )
    await sync_beta_assignment_progress(db, assignment=assignment)
    await db.commit()
    await db.refresh(assignment)
    return BetaReadSyncOut(
        assignment=await build_beta_read_assignment_out(
            db, assignment=assignment, current_user=current_user
        )
    )


@router.post(
    "/beta-reads/{assignment_id}/feedback-items",
    response_model=BetaReadAssignmentDetailOut,
    status_code=201,
)
async def create_beta_read_feedback_item(
    assignment_id: uuid.UUID,
    body: BetaReadFeedbackItemCreateBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    assignment = await get_beta_assignment_for_reader(
        db, assignment_id=assignment_id, current_user=current_user
    )
    await add_beta_read_feedback_item(
        db, assignment=assignment, current_user=current_user, body=body
    )
    await db.refresh(assignment)
    return await build_beta_read_assignment_detail_out(
        db, assignment=assignment, current_user=current_user
    )


@router.delete(
    "/beta-reads/{assignment_id}/feedback-items/{feedback_item_id}",
    response_model=BetaReadAssignmentDetailOut,
)
async def remove_beta_read_feedback_item(
    assignment_id: uuid.UUID,
    feedback_item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    assignment = await get_beta_assignment_for_reader(
        db, assignment_id=assignment_id, current_user=current_user
    )
    await delete_beta_read_feedback_item(
        db,
        assignment=assignment,
        feedback_item_id=feedback_item_id,
        current_user=current_user,
    )
    await db.refresh(assignment)
    return await build_beta_read_assignment_detail_out(
        db, assignment=assignment, current_user=current_user
    )


@router.put(
    "/books/{book_id}/beta-reads/{assignment_id}/feedback-items/{feedback_item_id}",
    response_model=BetaReadAssignmentDetailOut,
)
async def update_book_beta_read_feedback_item(
    book_id: uuid.UUID,
    assignment_id: uuid.UUID,
    feedback_item_id: uuid.UUID,
    body: BetaReadFeedbackItemAuthorUpdateBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    assignment = await get_beta_assignment_for_author(
        db, assignment_id=assignment_id, author_user_id=current_user.id
    )
    if assignment.book_id != book.id:
        raise HTTPException(404, "Beta read assignment not found.")
    await update_beta_read_feedback_item_author_state(
        db,
        assignment=assignment,
        feedback_item_id=feedback_item_id,
        author_status=body.author_status,
        author_task_id=body.author_task_id,
    )
    await db.refresh(assignment)
    return await build_beta_read_assignment_detail_out(db, assignment=assignment)


@router.post("/beta-reads/{assignment_id}/submit-feedback", response_model=BetaReadAssignmentOut)
async def submit_beta_read(
    assignment_id: uuid.UUID,
    body: BetaReadFeedbackSubmitBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    assignment = await get_beta_assignment_for_reader(
        db, assignment_id=assignment_id, current_user=current_user
    )
    assignment = await submit_beta_read_feedback(
        db,
        assignment=assignment,
        current_user=current_user,
        final_feedback=body.final_feedback,
        final_rating=body.final_rating,
    )
    await award_submitted_beta_reads(db, limit=20)
    await db.commit()
    await db.refresh(assignment)
    return await build_beta_read_assignment_out(
        db, assignment=assignment, current_user=current_user
    )
