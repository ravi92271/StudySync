"""SQLite storage using Python's built-in sqlite3 module."""

import sqlite3
from collections.abc import Iterator

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS classes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL UNIQUE COLLATE NOCASE,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS documents (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    class_id       INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    original_name  TEXT NOT NULL,
    stored_name    TEXT NOT NULL UNIQUE,
    file_type      TEXT NOT NULL,
    size_bytes     INTEGER NOT NULL,
    page_count     INTEGER,
    extracted_text TEXT NOT NULL,
    created_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS summaries (
    document_id     INTEGER PRIMARY KEY REFERENCES documents(id) ON DELETE CASCADE,
    overview        TEXT NOT NULL,
    key_points_json TEXT NOT NULL,
    model           TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS quizzes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    model       TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS quiz_questions (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    quiz_id           INTEGER NOT NULL REFERENCES quizzes(id) ON DELETE CASCADE,
    position          INTEGER NOT NULL,
    question          TEXT NOT NULL,
    choices_json      TEXT NOT NULL,
    answer_index      INTEGER NOT NULL,
    explanation       TEXT NOT NULL,
    source_quote      TEXT NOT NULL,
    quote_match       REAL NOT NULL,
    grounding_score   REAL NOT NULL,
    grounding_verdict TEXT NOT NULL,
    grounding_notes   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_documents_class ON documents(class_id);
CREATE INDEX IF NOT EXISTS idx_quizzes_document ON quizzes(document_id);
"""


def connect() -> sqlite3.Connection:
    config.data_dir().mkdir(parents=True, exist_ok=True)
    # FastAPI may run a request's setup and teardown on different threads, but a
    # connection is only ever used by one request at a time.
    conn = sqlite3.connect(config.db_path(), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")  # needed for ON DELETE CASCADE
    return conn


def init_db() -> None:
    config.upload_dir().mkdir(parents=True, exist_ok=True)
    conn = connect()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def get_db() -> Iterator[sqlite3.Connection]:
    """FastAPI dependency: one connection per request, committed on success."""
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
