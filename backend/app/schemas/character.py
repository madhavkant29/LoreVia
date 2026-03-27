from pydantic import BaseModel, ConfigDict
from datetime import datetime
import uuid


class TraitOut(BaseModel):
    value: str
    confidence: float   # 0.0–1.0
    type: str           # objective | subjective | abstract


class CharacterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    book_id: uuid.UUID
    name: str
    aliases: list[str] | None
    role: str | None
    first_chapter: int
    trait_state: dict | None
    hair: str | None
    eyes: str | None
    build: str | None
    age_descriptor: str | None
    distinguishing: str | None
    personality_tags: list[str] | None
    motivations: list[str] | None
    fears: list[str] | None
    archetype: str | None
    arc_summary: str | None
    created_at: datetime


class CharacterStateOut(BaseModel):
    character_id: uuid.UUID
    at_chapter: int
    trait_state: dict | None
    arc_note: str | None
    prompt_delta: str | None


class RelationshipOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    character_a_id: uuid.UUID
    character_b_id: uuid.UUID
    rel_type: str
    sentiment: float | None
    description: str | None
    from_chapter: int
    to_chapter: int | None
