"""Request and response shapes. Pydantic rejects anything that doesn't match."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from . import config
from .services.enhance import EnhanceOptions


def _clean_line(value: str) -> str:
    """Trim and collapse runs of whitespace in single-line fields."""
    return " ".join(value.split())


def clean_tags(tags: list[str]) -> list[str]:
    """Tidy tag names: no leading #, no commas, single spaces; drop empties and duplicates (ignoring case)."""
    out: list[str] = []
    for tag in tags:
        name = _clean_line(tag.replace(",", " ")).lstrip("#").strip()
        if not name:
            continue
        if len(name) > config.MAX_TAG:
            raise ValueError(f"Tags can be at most {config.MAX_TAG} characters.")
        if name.lower() not in (t.lower() for t in out):
            out.append(name)
    if len(out) > config.MAX_TAGS_PER_NOTE:
        raise ValueError(f"A note can have at most {config.MAX_TAGS_PER_NOTE} tags.")
    return out


class SubjectIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(max_length=config.MAX_SUBJECT)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        v = _clean_line(v)
        if not v:
            raise ValueError("Enter a subject name.")
        return v


class Subject(BaseModel):
    id: int
    name: str
    note_count: int


class NoteCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(default="", max_length=config.MAX_TITLE)
    topic: str = Field(default="", max_length=config.MAX_TOPIC)
    subject_id: int | None = None
    rough_text: str = Field(default="", max_length=config.MAX_ROUGH_TEXT)
    tags: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("title", "topic")
    @classmethod
    def clean(cls, v: str) -> str:
        return _clean_line(v)

    @field_validator("tags")
    @classmethod
    def tidy_tags(cls, v: list[str]) -> list[str]:
        return clean_tags(v)


class NoteUpdate(BaseModel):
    """Only the fields that are sent get updated (autosave sends what changed)."""
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(default=None, max_length=config.MAX_TITLE)
    topic: str | None = Field(default=None, max_length=config.MAX_TOPIC)
    subject_id: int | None = None
    rough_text: str | None = Field(default=None, max_length=config.MAX_ROUGH_TEXT)
    content: dict[str, Any] | None = None  # enhanced notes (editor JSON); null clears them
    options: EnhanceOptions | None = None
    source_hash: str | None = Field(default=None, max_length=64)
    content_edited: bool | None = None
    tags: list[str] | None = Field(default=None, max_length=100)

    @field_validator("title", "topic")
    @classmethod
    def clean(cls, v: str | None) -> str | None:
        return None if v is None else _clean_line(v)

    @field_validator("tags")
    @classmethod
    def tidy_tags(cls, v: list[str] | None) -> list[str] | None:
        return None if v is None else clean_tags(v)


class NoteSummary(BaseModel):
    id: int
    title: str
    topic: str
    subject_id: int | None
    subject_name: str | None
    created_at: str
    updated_at: str
    tags: list[str] = []


class Tag(BaseModel):
    name: str
    note_count: int


class Note(NoteSummary):
    rough_text: str
    content: dict[str, Any] | None = None
    options: EnhanceOptions | None = None
    source_hash: str | None = None
    content_edited: bool = False


class EnhanceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    options: EnhanceOptions = EnhanceOptions()
    force: bool = False  # enhance even if nothing changed since last time


class EnhanceResult(BaseModel):
    content: dict[str, Any]
    options: EnhanceOptions
    source_hash: str


class RegenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    blocks: list[dict[str, Any]] = Field(min_length=1, max_length=300)  # the section, heading first
    instruction: str = Field(default="", max_length=300)
    options: EnhanceOptions = EnhanceOptions()


class BlocksResult(BaseModel):
    blocks: list[dict[str, Any]]


class DiagramFixRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(min_length=1, max_length=6000)
    error: str = Field(default="", max_length=1000)


class DiagramFixResult(BaseModel):
    code: str


SortKey = Literal["updated", "created", "title"]
