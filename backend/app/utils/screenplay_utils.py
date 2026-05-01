"""
Screenplay utility helpers — scene management, dialogue analysis, 
screenplay statistics, and screenplay-specific operations.
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any, cast

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import Book, Dialogue, Scene
from app.schemas.books import DialogueOut, SceneAnalysis, SceneOut, ScreenplayStats

if TYPE_CHECKING:
    pass


# ─── Scene management ─────────────────────────────────────────────────────

async def get_owned_scene(db: AsyncSession, scene_id: uuid.UUID, user_id: uuid.UUID) -> Scene:
    """Get a scene if it belongs to the user."""
    result = await db.execute(
        select(Scene)
        .join(Book, Scene.book_id == Book.id)
        .where(Scene.id == scene_id, Book.user_id == user_id)
    )
    scene = result.scalar()
    if not scene:
        raise HTTPException(404, "Scene not found")
    return scene


async def list_scenes_for_book(db: AsyncSession, book_id: uuid.UUID, user_id: uuid.UUID) -> list[Scene]:
    """List all scenes for a book that belongs to the user."""
    result = await db.execute(
        select(Scene)
        .join(Book, Scene.book_id == Book.id)
        .where(Book.id == book_id, Book.user_id == user_id)
        .order_by(Scene.number)
    )
    return list(result.scalars().all())


async def get_scene_with_dialogue(db: AsyncSession, scene_id: uuid.UUID, user_id: uuid.UUID) -> Scene:
    """Get a scene with all its dialogue."""
    scene = await get_owned_scene(db, scene_id, user_id)

    dialogue_result = await db.execute(
        select(Dialogue)
        .where(Dialogue.scene_id == scene_id)
        .order_by(Dialogue.line_number)
    )
    dialogue = list(dialogue_result.scalars().all())

    scene.dialogue = dialogue
    return scene


async def scene_out(db: AsyncSession, scene: Scene) -> SceneOut:
    """Convert a scene to SceneOut schema with dialogue."""
    dialogue_result = await db.execute(
        select(Dialogue)
        .where(Dialogue.scene_id == scene.id)
        .order_by(Dialogue.line_number)
    )
    dialogue = list(dialogue_result.scalars().all())

    dialogue_out = [DialogueOut.model_validate(d) for d in dialogue]
    
    return SceneOut(
        id=scene.id,
        book_id=scene.book_id,
        chapter_id=scene.chapter_id,
        number=scene.number,
        heading=scene.heading,
        location=scene.location,
        time_of_day=scene.time_of_day,
        interior=scene.interior,
        exterior=scene.exterior,
        scene_number=scene.scene_number,
        description=scene.description,
        word_count=scene.word_count,
        page_number=scene.page_number,
        created_at=scene.created_at,
        dialogue=dialogue_out
    )


# ─── Screenplay statistics ───────────────────────────────────────────────

async def get_screenplay_stats(db: AsyncSession, book_id: uuid.UUID, user_id: uuid.UUID) -> ScreenplayStats:
    """Get comprehensive screenplay statistics."""
    # Verify book ownership
    book_result = await db.execute(select(Book).where(Book.id == book_id, Book.user_id == user_id))
    book = book_result.scalar()
    if not book:
        raise HTTPException(404, "Book not found")
    
    # Scene statistics
    scene_stats = cast(Any, (await db.execute(
        select(
            func.count(Scene.id).label('total_scenes'),
            func.sum(Scene.word_count).label('total_words'),
            func.sum(func.case((Scene.interior, 1), else_=0)).label('int_scenes'),
            func.sum(func.case((Scene.exterior, 1), else_=0)).label('ext_scenes')
        )
        .where(Scene.book_id == book_id)
    )).first())
    
    # Dialogue statistics
    dialogue_stats = cast(Any, (await db.execute(
        select(
            func.count(Dialogue.id).label('total_dialogue_lines'),
            func.sum(Dialogue.word_count).label('dialogue_words')
        )
        .join(Scene, Dialogue.scene_id == Scene.id)
        .where(Scene.book_id == book_id)
    )).first())
    
    # Character dialogue counts
    character_dialogue = (
        await db.execute(
            select(
                Dialogue.character_name,
                func.count(Dialogue.id).label('line_count')
            )
            .join(Scene, Dialogue.scene_id == Scene.id)
            .where(Scene.book_id == book_id)
            .group_by(Dialogue.character_name)
            .order_by(func.count(Dialogue.id).desc())
        )
    ).all()
    
    # Build stats
    total_scenes = scene_stats.total_scenes or 0
    total_dialogue_lines = dialogue_stats.total_dialogue_lines or 0
    total_words = (scene_stats.total_words or 0) + (dialogue_stats.dialogue_words or 0)
    
    # Estimate pages (1 page ≈ 1 minute of screen time)
    estimated_pages = max(1, round(total_words / 250))
    
    return ScreenplayStats(
        total_scenes=total_scenes,
        total_dialogue_lines=total_dialogue_lines,
        total_words=total_words,
        estimated_pages=estimated_pages,
        character_dialogue_counts={char: count for char, count in character_dialogue},
        scene_types={
            'INT': scene_stats.int_scenes or 0,
            'EXT': scene_stats.ext_scenes or 0,
            'OTHER': total_scenes - (scene_stats.int_scenes or 0) - (scene_stats.ext_scenes or 0)
        }
    )


async def get_scene_analysis(db: AsyncSession, scene_id: uuid.UUID, user_id: uuid.UUID) -> SceneAnalysis:
    """Get detailed analysis of a specific scene."""
    scene = await get_owned_scene(db, scene_id, user_id)

    # Get dialogue for this scene
    dialogue_result = await db.execute(
        select(Dialogue)
        .where(Dialogue.scene_id == scene_id)
        .order_by(Dialogue.line_number)
    )
    dialogue = list(dialogue_result.scalars().all())

    # Extract unique characters
    characters_present = list(set(d.character_name for d in dialogue))
    
    # Count dialogue lines and action lines
    dialogue_count = len(dialogue)
    action_lines = len(scene.description.split('\n')) if scene.description else 0
    
    # Estimate duration (roughly 1 minute per page)
    estimated_duration = None
    if scene.word_count:
        estimated_duration = round(scene.word_count / 250, 1)
    
    return SceneAnalysis(
        scene_number=scene.number,
        scene_heading=scene.heading,
        characters_present=characters_present,
        dialogue_count=dialogue_count,
        action_lines=action_lines,
        estimated_duration_minutes=estimated_duration
    )


# ─── Scene creation from screenplay text ───────────────────────────────────

async def create_scenes_from_screenplay(
    db: AsyncSession,
    book_id: uuid.UUID,
    screenplay_text: str
) -> list[Scene]:
    """Parse screenplay text and create scene models."""
    from app.parsers.screenplay_parser import create_scene_models, parse_screenplay
    
    scenes_data = parse_screenplay(screenplay_text)
    scene_models = create_scene_models(scenes_data, book_id)
    
    # Save to database
    created_scenes: list[Scene] = []
    for scene_model in scene_models:
        db.add(scene_model)
        await db.flush()  # Get the scene ID
        
        # Add dialogue
        for dialogue_model in scene_model.dialogue:
            dialogue_model.scene_id = scene_model.id
            db.add(dialogue_model)
        
        created_scenes.append(scene_model)
    
    await db.commit()
    return created_scenes


# ─── Character dialogue extraction ───────────────────────────────────────

async def get_character_dialogue(
    db: AsyncSession,
    book_id: uuid.UUID,
    character_name: str,
    user_id: uuid.UUID
) -> list[Dialogue]:
    """Get all dialogue lines for a specific character."""
    # Verify book ownership
    book_result = await db.execute(select(Book).where(Book.id == book_id, Book.user_id == user_id))
    book = book_result.scalar()
    if not book:
        raise HTTPException(404, "Book not found")
    
    dialogue_result = await db.execute(
        select(Dialogue)
        .join(Scene, Dialogue.scene_id == Scene.id)
        .where(
            Scene.book_id == book_id,
            Dialogue.character_name == character_name
        )
        .order_by(Scene.number, Dialogue.line_number)
    )
    return list(dialogue_result.scalars().all())


async def get_scene_by_location(
    db: AsyncSession,
    book_id: uuid.UUID,
    location: str,
    user_id: uuid.UUID
) -> list[Scene]:
    """Get all scenes at a specific location."""
    # Verify book ownership
    book_result = await db.execute(select(Book).where(Book.id == book_id, Book.user_id == user_id))
    book = book_result.scalar()
    if not book:
        raise HTTPException(404, "Book not found")
    
    scene_result = await db.execute(
        select(Scene)
        .where(
            Scene.book_id == book_id,
            func.lower(Scene.location) == func.lower(location)
        )
        .order_by(Scene.number)
    )
    return list(scene_result.scalars().all())


# ─── Scene search and filtering ───────────────────────────────────────────

async def search_scenes(
    db: AsyncSession,
    book_id: uuid.UUID,
    query: str,
    user_id: uuid.UUID
) -> list[Scene]:
    """Search scenes by heading, location, or description."""
    # Verify book ownership
    book_result = await db.execute(select(Book).where(Book.id == book_id, Book.user_id == user_id))
    book = book_result.scalar()
    if not book:
        raise HTTPException(404, "Book not found")
    
    search_pattern = f"%{query.lower()}%"
    
    scene_result = await db.execute(
        select(Scene)
        .where(
            Scene.book_id == book_id,
            (
                func.lower(Scene.heading).like(search_pattern) |
                func.lower(Scene.location).like(search_pattern) |
                func.lower(Scene.description).like(search_pattern)
            )
        )
        .order_by(Scene.number)
    )
    return list(scene_result.scalars().all())


async def filter_scenes_by_type(
    db: AsyncSession,
    book_id: uuid.UUID,
    scene_type: str,  # "INT", "EXT", or "ALL"
    user_id: uuid.UUID
) -> list[Scene]:
    """Filter scenes by interior/exterior type."""
    # Verify book ownership
    book_result = await db.execute(select(Book).where(Book.id == book_id, Book.user_id == user_id))
    book = book_result.scalar()
    if not book:
        raise HTTPException(404, "Book not found")
    
    query = select(Scene).where(Scene.book_id == book_id)
    
    if scene_type.upper() == "INT":
        query = query.where(Scene.interior)
    elif scene_type.upper() == "EXT":
        query = query.where(Scene.exterior)
    
    scene_result = await db.execute(query.order_by(Scene.number))
    return list(scene_result.scalars().all())
