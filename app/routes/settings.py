"""Settings (default options) and library backup / restore."""

import json
import sqlite3
from datetime import date
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from .. import config
from ..db import get_db, now
from ..schemas import clean_tags
from ..services.enhance import EnhanceOptions, content_text, validate_content
from .notes import set_tags, tags_by_note

router = APIRouter(prefix="/api", tags=["settings"])

BACKUP_VERSION = 1
MAX_BACKUP_BYTES = 50 * 1024 * 1024


# ---------- Settings ----------

class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    default_options: EnhanceOptions = EnhanceOptions()


def load_settings(db: sqlite3.Connection) -> Settings:
    row = db.execute("SELECT value FROM settings WHERE key = 'default_options'").fetchone()
    if not row:
        return Settings()
    try:
        return Settings(default_options=EnhanceOptions.model_validate_json(row["value"]))
    except ValidationError:
        return Settings()


@router.get("/settings")
def get_settings(db: sqlite3.Connection = Depends(get_db)) -> Settings:
    return load_settings(db)


@router.put("/settings")
def put_settings(body: Settings, db: sqlite3.Connection = Depends(get_db)) -> Settings:
    db.execute(
        "INSERT INTO settings (key, value) VALUES ('default_options', ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (body.default_options.model_dump_json(),),
    )
    return body


# ---------- Backup ----------

class BackupSubject(BaseModel):
    id: int
    name: str = Field(min_length=1, max_length=config.MAX_SUBJECT)
    created_at: str = Field(max_length=40)


class BackupNote(BaseModel):
    subject_id: int | None = None
    title: str = Field(default="", max_length=config.MAX_TITLE)
    topic: str = Field(default="", max_length=config.MAX_TOPIC)
    rough_text: str = Field(default="", max_length=config.MAX_ROUGH_TEXT)
    content: dict[str, Any] | None = None
    options: EnhanceOptions | None = None
    source_hash: str | None = Field(default=None, max_length=64)
    content_edited: bool = False
    created_at: str = Field(max_length=40)
    updated_at: str = Field(max_length=40)
    tags: list[str] = Field(default_factory=list, max_length=100)  # added after version 1; optional

    @field_validator("tags")
    @classmethod
    def tidy_tags(cls, v: list[str]) -> list[str]:
        return clean_tags(v)


class Backup(BaseModel):
    app: Literal["margin"]
    version: int
    exported_at: str = ""
    subjects: list[BackupSubject] = Field(default_factory=list, max_length=5000)
    notes: list[BackupNote] = Field(default_factory=list, max_length=20000)
    settings: Settings | None = None


@router.get("/backup")
def backup(db: sqlite3.Connection = Depends(get_db)) -> Response:
    subjects = [dict(r) for r in db.execute("SELECT id, name, created_at FROM subjects ORDER BY id")]
    notes = []
    rows = [dict(r) for r in db.execute(
        """SELECT id, subject_id, title, topic, rough_text, content_json, options_json, source_hash,
                  content_edited, created_at, updated_at FROM notes ORDER BY id"""
    )]
    tags = tags_by_note(db, [r["id"] for r in rows])
    for note in rows:
        note["tags"] = tags.get(note.pop("id"), [])
        note["content"] = json.loads(note.pop("content_json") or "null")
        note["options"] = json.loads(note.pop("options_json") or "null")
        note["content_edited"] = bool(note["content_edited"])
        notes.append(note)
    payload = {
        "app": "margin", "version": BACKUP_VERSION, "exported_at": now(),
        "subjects": subjects, "notes": notes, "settings": load_settings(db).model_dump(),
    }
    name = f"margin-backup-{date.today().isoformat()}.json"
    return Response(
        json.dumps(payload, ensure_ascii=False, indent=1),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{name}"', "Cache-Control": "no-store"},
    )


class RestoreResult(BaseModel):
    notes: int
    subjects_created: int


@router.post("/restore")
async def restore(
    request: Request, mode: Literal["merge", "replace"] = "merge", db: sqlite3.Connection = Depends(get_db),
) -> RestoreResult:
    """merge: add the backup's notes to the library. replace: delete everything first."""
    size = int(request.headers.get("content-length") or 0)
    if size > MAX_BACKUP_BYTES:
        raise HTTPException(413, "This backup file is too large.")
    raw = await request.body()
    if len(raw) > MAX_BACKUP_BYTES:
        raise HTTPException(413, "This backup file is too large.")
    try:
        data = Backup.model_validate_json(raw)
    except ValidationError:
        raise HTTPException(422, "This file isn't a Margin backup, or it is damaged.")
    if data.version > BACKUP_VERSION:
        raise HTTPException(422, "This backup was made by a newer version of Margin.")

    # Check every note before changing anything
    prepared = []
    for note in data.notes:
        content_json, text = None, ""
        if note.content is not None:
            try:
                clean = validate_content(note.content)
            except ValueError:
                raise HTTPException(422, "This backup contains notes in an unexpected format.")
            content_json, text = json.dumps(clean, ensure_ascii=False), content_text(clean)
        prepared.append((note, content_json, text))

    db.execute("BEGIN")
    try:
        if mode == "replace":
            db.execute("DELETE FROM notes")
            db.execute("DELETE FROM subjects")
            db.execute("DELETE FROM tags")
        existing = {r["name"].lower(): r["id"] for r in db.execute("SELECT id, name FROM subjects")}
        id_map, created = {}, 0
        for s in data.subjects:
            key = s.name.strip().lower()
            if key not in existing:
                cur = db.execute("INSERT INTO subjects (name, created_at) VALUES (?, ?)", (s.name.strip(), s.created_at))
                existing[key] = cur.lastrowid
                created += 1
            id_map[s.id] = existing[key]
        for note, content_json, text in prepared:
            cur = db.execute(
                """INSERT INTO notes (subject_id, title, topic, rough_text, content_json, content_text,
                       options_json, source_hash, content_edited, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (id_map.get(note.subject_id), note.title, note.topic, note.rough_text, content_json, text,
                 note.options.model_dump_json() if note.options else None, note.source_hash,
                 int(note.content_edited), note.created_at, note.updated_at),
            )
            if note.tags:
                set_tags(db, cur.lastrowid, note.tags)
        if mode == "replace" and data.settings:
            db.execute(
                "INSERT INTO settings (key, value) VALUES ('default_options', ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (data.settings.default_options.model_dump_json(),),
            )
        db.execute("COMMIT")
    except Exception:
        db.execute("ROLLBACK")
        raise
    return RestoreResult(notes=len(prepared), subjects_created=created)
