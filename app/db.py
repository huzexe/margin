"""SQLite database: connection handling and table setup."""

import sqlite3
from collections.abc import Iterator
from datetime import datetime, timezone

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS subjects (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE COLLATE NOCASE,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notes (
    id            INTEGER PRIMARY KEY,
    subject_id    INTEGER REFERENCES subjects(id) ON DELETE SET NULL,
    title         TEXT NOT NULL DEFAULT '',
    topic         TEXT NOT NULL DEFAULT '',
    rough_text    TEXT NOT NULL DEFAULT '',
    content_json  TEXT,            -- enhanced notes (Phase 2)
    content_text  TEXT NOT NULL DEFAULT '',  -- plain text of content_json, for search
    options_json  TEXT,            -- options used for the last enhance (Phase 2)
    source_hash   TEXT,            -- detects "nothing changed since last enhance"
    content_edited INTEGER NOT NULL DEFAULT 0,  -- 1 once the user edits enhanced notes
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS notes_subject ON notes(subject_id);
CREATE INDEX IF NOT EXISTS notes_updated ON notes(updated_at);

CREATE TABLE IF NOT EXISTS tags (
    id    INTEGER PRIMARY KEY,
    name  TEXT NOT NULL UNIQUE COLLATE NOCASE
);

CREATE TABLE IF NOT EXISTS note_tags (
    note_id  INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
    tag_id   INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (note_id, tag_id)
);

CREATE INDEX IF NOT EXISTS note_tags_tag ON note_tags(tag_id);

CREATE TABLE IF NOT EXISTS settings (
    key    TEXT PRIMARY KEY,
    value  TEXT NOT NULL
);

-- Full-text search index, kept in sync with notes by triggers
CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
    title, topic, rough_text, content_text,
    content='notes', content_rowid='id',
    tokenize='unicode61 remove_diacritics 2'
);

CREATE TRIGGER IF NOT EXISTS notes_ai AFTER INSERT ON notes BEGIN
    INSERT INTO notes_fts(rowid, title, topic, rough_text, content_text)
    VALUES (new.id, new.title, new.topic, new.rough_text, new.content_text);
END;

CREATE TRIGGER IF NOT EXISTS notes_ad AFTER DELETE ON notes BEGIN
    INSERT INTO notes_fts(notes_fts, rowid, title, topic, rough_text, content_text)
    VALUES ('delete', old.id, old.title, old.topic, old.rough_text, old.content_text);
END;

CREATE TRIGGER IF NOT EXISTS notes_au AFTER UPDATE ON notes BEGIN
    INSERT INTO notes_fts(notes_fts, rowid, title, topic, rough_text, content_text)
    VALUES ('delete', old.id, old.title, old.topic, old.rough_text, old.content_text);
    INSERT INTO notes_fts(rowid, title, topic, rough_text, content_text)
    VALUES (new.id, new.title, new.topic, new.rough_text, new.content_text);
END;
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Autocommit: each write is saved immediately, before the response is sent.
    # check_same_thread=False because FastAPI may open and use the connection on
    # different worker threads; each request still gets its own connection.
    conn = sqlite3.connect(config.DB_PATH, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


# Columns added after the first release: (table, column, definition)
MIGRATIONS = [
    ("notes", "content_edited", "INTEGER NOT NULL DEFAULT 0"),
]


def init() -> None:
    conn = connect()
    try:
        conn.executescript(SCHEMA)
        for table, column, definition in MIGRATIONS:
            existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
            if column not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
    finally:
        conn.close()


def get_db() -> Iterator[sqlite3.Connection]:
    """FastAPI dependency: one connection per request."""
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()
