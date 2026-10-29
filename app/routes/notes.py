"""Notes API: list/search, create, read, autosave updates, delete."""

import json
import re
import sqlite3
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.concurrency import run_in_threadpool

from .. import config
from ..db import get_db, now
from ..schemas import (
    BlocksResult, DiagramFixRequest, DiagramFixResult, EnhanceRequest, EnhanceResult, Note, NoteCreate,
    NoteSummary, NoteUpdate, RegenerateRequest, SortKey, Tag,
)
from ..services import llm, pdf, prompts
from ..services.pdf import PdfSettings
from ..services.enhance import (
    DiagramFix, EnhancedNotes, Section, block_heading, blocks_to_text, content_text, outline_except,
    section_blocks, source_hash, to_editor, validate_content,
)

router = APIRouter(prefix="/api/notes", tags=["notes"])

SELECT = """
SELECT n.id, n.title, n.topic, n.subject_id, s.name AS subject_name,
       n.created_at, n.updated_at {extra}
FROM notes n LEFT JOIN subjects s ON s.id = n.subject_id
"""

ORDER = {
    "updated": "n.updated_at DESC, n.id DESC",
    "created": "n.created_at DESC, n.id DESC",
    "title": "CASE WHEN n.title = '' THEN 1 ELSE 0 END, n.title COLLATE NOCASE, n.id",
}


def fts_query(text: str) -> str | None:
    """Turn what the user typed into a safe FTS5 query: every word must match as a prefix."""
    words = re.findall(r"\w+", text, flags=re.UNICODE)
    if not words:
        return None
    return " ".join(f'"{w}"*' for w in words[:12])


def _check_subject(db: sqlite3.Connection, subject_id: int | None) -> None:
    if subject_id is not None and not db.execute(
        "SELECT 1 FROM subjects WHERE id = ?", (subject_id,)
    ).fetchone():
        raise HTTPException(422, "That subject no longer exists.")


def tags_by_note(db: sqlite3.Connection, note_ids: list[int]) -> dict[int, list[str]]:
    if not note_ids:
        return {}
    marks = ",".join("?" * len(note_ids))
    out: dict[int, list[str]] = {}
    for row in db.execute(
        f"""SELECT nt.note_id, t.name FROM note_tags nt JOIN tags t ON t.id = nt.tag_id
            WHERE nt.note_id IN ({marks}) ORDER BY t.name COLLATE NOCASE""",
        note_ids,
    ):
        out.setdefault(row["note_id"], []).append(row["name"])
    return out


def set_tags(db: sqlite3.Connection, note_id: int, names: list[str]) -> None:
    """Replace a note's tags. Tags no note uses any more are removed."""
    db.execute("DELETE FROM note_tags WHERE note_id = ?", (note_id,))
    for name in names:
        db.execute("INSERT INTO tags (name) VALUES (?) ON CONFLICT(name) DO NOTHING", (name,))
        db.execute(
            "INSERT OR IGNORE INTO note_tags (note_id, tag_id) SELECT ?, id FROM tags WHERE name = ?",
            (note_id, name),
        )
    db.execute("DELETE FROM tags WHERE id NOT IN (SELECT tag_id FROM note_tags)")


def _get(db: sqlite3.Connection, note_id: int) -> Note:
    row = db.execute(
        SELECT.format(extra=", n.rough_text, n.content_json, n.options_json, n.source_hash, n.content_edited")
        + " WHERE n.id = ?",
        (note_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(404, "Note not found.")
    data = dict(row)
    data["content"] = json.loads(data.pop("content_json") or "null")
    data["options"] = json.loads(data.pop("options_json") or "null")
    data["content_edited"] = bool(data["content_edited"])
    data["tags"] = tags_by_note(db, [note_id]).get(note_id, [])
    return Note(**data)


def _content_columns(content: dict | None) -> dict:
    """Validate enhanced notes and return the columns that store them."""
    if content is None:
        return {"content_json": None, "content_text": ""}
    try:
        clean = validate_content(content)
    except ValueError as e:
        raise HTTPException(422, str(e))
    encoded = json.dumps(clean, ensure_ascii=False)
    if len(encoded.encode()) > config.MAX_CONTENT_BYTES:
        raise HTTPException(422, "Enhanced notes are too long to save.")
    return {"content_json": encoded, "content_text": content_text(clean)}


@router.get("")
def list_notes(
    q: str = Query(default="", max_length=200),
    subject_id: int | None = None,
    tag: str | None = Query(default=None, max_length=config.MAX_TAG + 1),
    sort: SortKey = "updated",
    db: sqlite3.Connection = Depends(get_db),
) -> list[NoteSummary]:
    where, params = [], []
    match = fts_query(q)
    if match:
        # Text matches, or a tag that starts with what was typed ("#exa" finds the tag "exam")
        where.append(
            """(n.id IN (SELECT rowid FROM notes_fts WHERE notes_fts MATCH ?)
                OR n.id IN (SELECT nt.note_id FROM note_tags nt JOIN tags t ON t.id = nt.tag_id
                            WHERE t.name LIKE ? ESCAPE '\\'))"""
        )
        prefix = re.sub(r"([%_\\])", r"\\\1", q.strip().lstrip("#"))
        params += [match, prefix + "%"]
    if subject_id is not None:
        where.append("n.subject_id = ?")
        params.append(subject_id)
    if tag:
        where.append(
            "n.id IN (SELECT nt.note_id FROM note_tags nt JOIN tags t ON t.id = nt.tag_id WHERE t.name = ?)"
        )
        params.append(tag)
    sql = SELECT.format(extra="")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY " + ORDER[sort]
    rows = [dict(row) for row in db.execute(sql, params)]
    tags = tags_by_note(db, [r["id"] for r in rows])
    return [NoteSummary(**r, tags=tags.get(r["id"], [])) for r in rows]


tags_router = APIRouter(prefix="/api/tags", tags=["tags"])


@tags_router.get("")
def list_tags(db: sqlite3.Connection = Depends(get_db)) -> list[Tag]:
    return [Tag(**row) for row in db.execute(
        """SELECT t.name, COUNT(nt.note_id) AS note_count FROM tags t
           JOIN note_tags nt ON nt.tag_id = t.id GROUP BY t.id ORDER BY t.name COLLATE NOCASE"""
    )]


@router.post("", status_code=201)
def create_note(body: NoteCreate, db: sqlite3.Connection = Depends(get_db)) -> Note:
    _check_subject(db, body.subject_id)
    ts = now()
    cur = db.execute(
        """INSERT INTO notes (title, topic, subject_id, rough_text, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (body.title, body.topic, body.subject_id, body.rough_text, ts, ts),
    )
    if body.tags:
        set_tags(db, cur.lastrowid, body.tags)
    return _get(db, cur.lastrowid)


@router.get("/{note_id}")
def get_note(note_id: int, db: sqlite3.Connection = Depends(get_db)) -> Note:
    return _get(db, note_id)


@router.patch("/{note_id}")
def update_note(
    note_id: int, body: NoteUpdate, db: sqlite3.Connection = Depends(get_db)
) -> Note:
    _get(db, note_id)
    changes = body.model_dump(exclude_unset=True)
    # Most fields can't be null; subject_id null means "No subject", content null clears it
    changes = {k: v for k, v in changes.items() if v is not None or k in ("subject_id", "content")}
    if "subject_id" in changes:
        _check_subject(db, changes["subject_id"])
    if "content" in changes:
        changes.update(_content_columns(changes.pop("content")))
    if "options" in changes:
        changes["options_json"] = json.dumps(changes.pop("options"))
    if "content_edited" in changes:
        changes["content_edited"] = int(changes["content_edited"])
    if "tags" in changes:
        set_tags(db, note_id, changes.pop("tags"))
        changes.setdefault("updated_at", now())
    if changes:
        changes["updated_at"] = now()
        cols = ", ".join(f"{k} = ?" for k in changes)  # keys come from the schema, not the user
        db.execute(f"UPDATE notes SET {cols} WHERE id = ?", (*changes.values(), note_id))
    return _get(db, note_id)


@router.post("/{note_id}/enhance")
async def enhance_note(
    note_id: int, body: EnhanceRequest, db: sqlite3.Connection = Depends(get_db)
) -> EnhanceResult:
    """Turn the saved rough notes into structured notes. The result is returned,
    not saved: the page shows it and saves it, so a cancelled request changes nothing."""
    note = _get(db, note_id)
    if not note.rough_text.strip():
        raise HTTPException(422, "Write some rough notes first.")

    digest = source_hash(
        title=note.title, topic=note.topic, subject=note.subject_name,
        rough_text=note.rough_text, options=body.options,
    )
    if not body.force and note.content and note.source_hash == digest:
        raise HTTPException(409, "unchanged")

    prompt = prompts.build_prompt(
        title=note.title, subject=note.subject_name, topic=note.topic,
        rough_text=note.rough_text, options=body.options,
    )
    doc = await run_in_threadpool(llm.generate_json, prompts.SYSTEM, prompt, EnhancedNotes)
    content = to_editor(doc)
    if not content["blocks"]:
        raise llm.LLMError(llm.MSG_FAILED)
    return EnhanceResult(content=content, options=body.options, source_hash=digest)


@router.post("/{note_id}/regenerate-section")
async def regenerate_section(
    note_id: int, body: RegenerateRequest, db: sqlite3.Connection = Depends(get_db)
) -> BlocksResult:
    """Rewrite one section (heading + its blocks). Returned, not saved, like enhance."""
    note = _get(db, note_id)
    try:
        validate_content({"blocks": body.blocks})
    except ValueError as e:
        raise HTTPException(422, str(e))
    section_text = blocks_to_text(body.blocks)
    if not section_text.strip():
        raise HTTPException(422, "This section is empty.")

    heading = block_heading(body.blocks[0])
    prompt = prompts.build_regenerate_prompt(
        title=note.title, subject=note.subject_name, topic=note.topic, rough_text=note.rough_text,
        options=body.options, section_text=section_text, instruction=body.instruction,
        elsewhere=outline_except(note.content, heading),
    )
    section = await run_in_threadpool(llm.generate_json, prompts.SYSTEM, prompt, Section, max_tokens=8000)
    blocks = section_blocks(section)
    if not blocks:
        raise llm.LLMError(llm.MSG_FAILED)
    return BlocksResult(blocks=blocks)


@router.post("/diagrams/fix", tags=["diagrams"])
async def fix_diagram(body: DiagramFixRequest) -> DiagramFixResult:
    """Ask for a corrected version of Mermaid code that failed to render."""
    fixed = await run_in_threadpool(
        llm.generate_json, "You fix Mermaid diagram code.", prompts.build_fix_prompt(body.code, body.error),
        DiagramFix, max_tokens=4000, temperature=0.1,
    )
    code = fixed.mermaid.strip().removeprefix("```mermaid").removeprefix("```").removesuffix("```").strip()
    if not code:
        raise llm.LLMError(llm.MSG_FAILED)
    return DiagramFixResult(code=code)


@router.get("/{note_id}/pdf")
async def note_pdf(
    note_id: int, request: Request, settings: PdfSettings = Depends(),
    db: sqlite3.Connection = Depends(get_db),
) -> Response:
    note = _get(db, note_id)
    # The PDF browser always opens the print page via this computer's own address,
    # even when a phone asked for the PDF (so it never needs the PIN)
    data = await pdf.render(f"http://127.0.0.1:{request.url.port or config.PORT}/", note_id, settings)
    name = pdf.filename(note.title or "Untitled note")
    ascii_name = name.encode("ascii", "ignore").decode() or "Margin-note.pdf"
    return Response(data, media_type="application/pdf", headers={
        "Content-Disposition": f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(name)}",
        "Cache-Control": "no-store",
    })


@router.delete("/{note_id}", status_code=204)
def delete_note(note_id: int, db: sqlite3.Connection = Depends(get_db)) -> Response:
    _get(db, note_id)
    db.execute("DELETE FROM notes WHERE id = ?", (note_id,))
    return Response(status_code=204)
