import re
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.api.deps.rate_limit import enforce_manuscript_import_rate_limit, rate_limit_upload
from app.core.config import settings
from app.core.database import get_db
from app.schemas.books import (
    ManuscriptImportResult,
    RevisionRoundComparisonOut,
    RevisionRoundCreateBody,
    RevisionRoundListOut,
    RevisionRoundOut,
    WorkflowBridgePreviewOut,
)
from app.services.processing_allowance_service import ensure_project_writable
from app.services.workflow_bridge_service import apply_workflow_bridge_import
from app.utils.billing_utils import require_author_access
from app.utils.books.normalization import resolve_upload_format_and_work_type
from app.utils.books.notes import get_owned_book
from app.utils.books.revision_milestones import (
    compare_revision_rounds,
    create_revision_round,
    list_revision_rounds,
)
from app.utils.books.workflow_bridge import (
    build_workflow_preview_token,
    export_book_to_scrivener,
    load_workflow_book_state_digest,
    preview_workflow_import,
    verify_workflow_preview_token,
)
from app.utils.upload_security_utils import read_upload_bounded, validate_document_upload_bytes

router = APIRouter()


@router.get("/{book_id}/revision-rounds", response_model=RevisionRoundListOut)
async def get_revision_rounds(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    return RevisionRoundListOut(
        items=[RevisionRoundOut(**item) for item in list_revision_rounds(book)]
    )


@router.post("/{book_id}/revision-rounds", response_model=RevisionRoundOut, status_code=201)
async def snapshot_revision_round(
    book_id: uuid.UUID,
    body: RevisionRoundCreateBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    await ensure_project_writable(db, book)
    return RevisionRoundOut(
        **(
            await create_revision_round(
                db,
                book=book,
                label=body.label,
                note=body.note,
            )
        )
    )


@router.get(
    "/{book_id}/revision-rounds/{base_round_id}/compare",
    response_model=RevisionRoundComparisonOut,
)
async def compare_revision_round(
    book_id: uuid.UUID,
    base_round_id: str,
    target_round_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    return RevisionRoundComparisonOut(
        **(
            await compare_revision_rounds(
                db,
                book=book,
                base_round_id=base_round_id,
                target_round_id=target_round_id,
            )
        )
    )


@router.post("/{book_id}/workflow-bridge/preview", response_model=WorkflowBridgePreviewOut)
async def preview_external_manuscript(
    book_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(rate_limit_upload),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    if not file.filename:
        raise HTTPException(400, "Choose a DOCX or Scrivener project to preview.")
    format_name, work_type = resolve_upload_format_and_work_type(file.filename, book.work_type)
    if work_type == "screenplay" or format_name not in {"docx", "scrivener"}:
        raise HTTPException(400, "Workflow Bridge currently accepts DOCX and Scrivener projects.")
    raw = await read_upload_bounded(
        file, settings.MANUSCRIPT_IMPORT_MAX_BYTES, "Workflow Bridge file"
    )
    validate_document_upload_bytes(file.filename, raw, format_name)
    preview = await preview_workflow_import(
        db,
        book=book,
        filename=file.filename,
        raw=raw,
        format_name=format_name,
    )
    return WorkflowBridgePreviewOut(
        **preview,
        preview_token=build_workflow_preview_token(
            user_id=current_user.id,
            book_id=book.id,
            format_name=format_name,
            raw=raw,
            book_state_digest=str(preview["book_state_digest"]),
        ),
    )


@router.post("/{book_id}/workflow-bridge/apply", response_model=ManuscriptImportResult)
async def apply_external_manuscript(
    book_id: uuid.UUID,
    file: UploadFile = File(...),
    preview_token: str = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(rate_limit_upload),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    await ensure_project_writable(db, book)
    if not file.filename:
        raise HTTPException(400, "Choose a DOCX or Scrivener project to apply.")
    format_name, work_type = resolve_upload_format_and_work_type(file.filename, book.work_type)
    if work_type == "screenplay" or format_name not in {"docx", "scrivener"}:
        raise HTTPException(400, "Workflow Bridge currently accepts DOCX and Scrivener projects.")
    raw = await read_upload_bounded(
        file, settings.MANUSCRIPT_IMPORT_MAX_BYTES, "Workflow Bridge file"
    )
    validate_document_upload_bytes(file.filename, raw, format_name)
    await enforce_manuscript_import_rate_limit(db, current_user.id)
    book_state_digest = await load_workflow_book_state_digest(
        db,
        book_id=book.id,
        lock_for_update=True,
    )
    verify_workflow_preview_token(
        preview_token,
        user_id=current_user.id,
        book_id=book.id,
        format_name=format_name,
        raw=raw,
        book_state_digest=book_state_digest,
    )
    return await apply_workflow_bridge_import(
        db,
        book=book,
        current_user=current_user,
        filename=file.filename,
        raw=raw,
        format_name=format_name,
    )


@router.get("/{book_id}/workflow-bridge/scrivener")
async def export_external_scrivener_project(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    archive = await export_book_to_scrivener(db, book=book)
    stem = re.sub(r"[^A-Za-z0-9_-]+", "-", book.title).strip("-") or "LoreVia-Project"
    return Response(
        content=archive,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{stem}.scrivzip"'},
    )
