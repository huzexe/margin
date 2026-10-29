"""Subjects API: list, add, rename, delete. Subjects only exist if the user adds them."""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Response

from ..db import get_db, now
from ..schemas import Subject, SubjectIn

router = APIRouter(prefix="/api/subjects", tags=["subjects"])

LIST_SQL = """
SELECT s.id, s.name, COUNT(n.id) AS note_count
FROM subjects s LEFT JOIN notes n ON n.subject_id = s.id
{where}
GROUP BY s.id
ORDER BY s.name COLLATE NOCASE
"""


def _get(db: sqlite3.Connection, subject_id: int) -> Subject:
    row = db.execute(LIST_SQL.format(where="WHERE s.id = ?"), (subject_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Subject not found.")
    return Subject(**row)


@router.get("")
def list_subjects(db: sqlite3.Connection = Depends(get_db)) -> list[Subject]:
    return [Subject(**row) for row in db.execute(LIST_SQL.format(where=""))]


@router.post("", status_code=201)
def create_subject(body: SubjectIn, db: sqlite3.Connection = Depends(get_db)) -> Subject:
    try:
        cur = db.execute(
            "INSERT INTO subjects (name, created_at) VALUES (?, ?)", (body.name, now())
        )
    except sqlite3.IntegrityError:
        raise HTTPException(409, "This subject already exists.")
    return _get(db, cur.lastrowid)


@router.patch("/{subject_id}")
def rename_subject(
    subject_id: int, body: SubjectIn, db: sqlite3.Connection = Depends(get_db)
) -> Subject:
    _get(db, subject_id)
    try:
        db.execute("UPDATE subjects SET name = ? WHERE id = ?", (body.name, subject_id))
    except sqlite3.IntegrityError:
        raise HTTPException(409, "This subject already exists.")
    return _get(db, subject_id)


@router.delete("/{subject_id}", status_code=204)
def delete_subject(subject_id: int, db: sqlite3.Connection = Depends(get_db)) -> Response:
    """Deletes the subject only. Its notes stay and become 'No subject'."""
    _get(db, subject_id)
    db.execute("DELETE FROM subjects WHERE id = ?", (subject_id,))
    return Response(status_code=204)
