"""HTTP routes."""

import json
import sqlite3
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from . import config, extraction, llm
from .db import get_db
from .schemas import (
    ClassCreate,
    ClassOut,
    DocumentDetail,
    DocumentSummary,
    LLMStatus,
    QuizOut,
    QuizRequest,
    SummaryOut,
)

router = APIRouter()
Db = sqlite3.Connection

DOC_LIST_COLUMNS = (
    "id, class_id, original_name, file_type, size_bytes, page_count, "
    "length(extracted_text) AS char_count, created_at"
)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _document_row(db: Db, document_id: int) -> sqlite3.Row:
    row = db.execute(
        f"SELECT {DOC_LIST_COLUMNS}, extracted_text, stored_name FROM documents WHERE id = ?",
        (document_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(404, "Document not found.")
    return row


def _stored_path(stored_name: str) -> Path:
    return config.upload_dir() / stored_name


def _remove_files(stored_names: list[str]) -> None:
    for name in stored_names:
        _stored_path(name).unlink(missing_ok=True)


def _summary_for(db: Db, document_id: int) -> SummaryOut | None:
    row = db.execute("SELECT * FROM summaries WHERE document_id = ?", (document_id,)).fetchone()
    if row is None:
        return None
    return SummaryOut(
        overview=row["overview"],
        key_points=json.loads(row["key_points_json"]),
        model=row["model"],
        created_at=row["created_at"],
    )


def _quiz_by_id(db: Db, quiz_id: int) -> QuizOut:
    quiz = db.execute("SELECT * FROM quizzes WHERE id = ?", (quiz_id,)).fetchone()
    rows = db.execute(
        "SELECT * FROM quiz_questions WHERE quiz_id = ? ORDER BY position", (quiz_id,)
    ).fetchall()
    return QuizOut(
        id=quiz["id"],
        model=quiz["model"],
        created_at=quiz["created_at"],
        questions=[
            {**{k: r[k] for k in r.keys() if k not in ("choices_json", "quiz_id", "position")},
             "choices": json.loads(r["choices_json"])}
            for r in rows
        ],
    )


def _latest_quiz(db: Db, document_id: int) -> QuizOut | None:
    row = db.execute(
        "SELECT id FROM quizzes WHERE document_id = ? ORDER BY id DESC LIMIT 1", (document_id,)
    ).fetchone()
    return _quiz_by_id(db, row["id"]) if row else None


def _llm_call(fn, *args):
    """Run an LLM function, turning its errors into clear HTTP errors."""
    try:
        return fn(*args)
    except llm.LLMUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    except llm.LLMOutputError as exc:
        raise HTTPException(502, f"{exc} Try again, or try a larger model.") from exc


# --------------------------------------------------------------------------- #
# Status
# --------------------------------------------------------------------------- #


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/llm/status", response_model=LLMStatus)
def llm_status():
    return llm.status()


# --------------------------------------------------------------------------- #
# Classes
# --------------------------------------------------------------------------- #


@router.get("/classes", response_model=list[ClassOut])
def list_classes(db: Db = Depends(get_db)):
    rows = db.execute(
        """SELECT c.id, c.name, c.created_at, COUNT(d.id) AS document_count
           FROM classes c LEFT JOIN documents d ON d.class_id = c.id
           GROUP BY c.id ORDER BY c.name"""
    ).fetchall()
    return [dict(r) for r in rows]


@router.post("/classes", response_model=ClassOut, status_code=201)
def create_class(payload: ClassCreate, db: Db = Depends(get_db)):
    name = payload.name.strip()
    if not name:
        raise HTTPException(422, "Class name cannot be blank.")
    try:
        cur = db.execute("INSERT INTO classes (name) VALUES (?)", (name,))
    except sqlite3.IntegrityError:
        raise HTTPException(409, f"You already have a class named '{name}'.") from None
    row = db.execute("SELECT id, name, created_at FROM classes WHERE id = ?", (cur.lastrowid,)).fetchone()
    return {**dict(row), "document_count": 0}


@router.delete("/classes/{class_id}", status_code=204)
def delete_class(class_id: int, db: Db = Depends(get_db)):
    if db.execute("SELECT 1 FROM classes WHERE id = ?", (class_id,)).fetchone() is None:
        raise HTTPException(404, "Class not found.")
    stored = [r["stored_name"] for r in db.execute(
        "SELECT stored_name FROM documents WHERE class_id = ?", (class_id,))]
    db.execute("DELETE FROM classes WHERE id = ?", (class_id,))  # cascades to documents
    db.commit()
    _remove_files(stored)


# --------------------------------------------------------------------------- #
# Documents
# --------------------------------------------------------------------------- #


@router.get("/classes/{class_id}/documents", response_model=list[DocumentSummary])
def list_documents(class_id: int, db: Db = Depends(get_db)):
    if db.execute("SELECT 1 FROM classes WHERE id = ?", (class_id,)).fetchone() is None:
        raise HTTPException(404, "Class not found.")
    rows = db.execute(
        f"SELECT {DOC_LIST_COLUMNS} FROM documents WHERE class_id = ? ORDER BY id DESC", (class_id,)
    ).fetchall()
    return [dict(r) for r in rows]


@router.post("/classes/{class_id}/documents", response_model=DocumentDetail, status_code=201)
def upload_document(class_id: int, file: UploadFile = File(...), db: Db = Depends(get_db)):
    """Upload a PDF, Word (.docx) or PowerPoint (.pptx) file to a class."""
    if db.execute("SELECT 1 FROM classes WHERE id = ?", (class_id,)).fetchone() is None:
        raise HTTPException(404, "Class not found.")

    original_name = Path(file.filename or "").name or "upload"
    suffix = Path(original_name).suffix.lower()
    file_type = extraction.SUPPORTED_TYPES.get(suffix)
    if file_type is None:
        raise HTTPException(
            415,
            "Unsupported file type. Upload a PDF, Word (.docx) or PowerPoint (.pptx) file. "
            "Older .doc and .ppt files need to be re-saved in the newer format first.",
        )

    # Stream to disk under a random name (never trust the client's filename for paths).
    stored_name = f"{uuid.uuid4().hex}{suffix}"
    path = _stored_path(stored_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    size = 0
    try:
        with path.open("wb") as out:
            head = b""
            while chunk := file.file.read(1024 * 1024):
                if not head:
                    head = chunk[:8]
                size += len(chunk)
                if size > config.MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        413, f"File is too large (limit {config.MAX_UPLOAD_BYTES // (1024 * 1024)} MB)."
                    )
                out.write(chunk)
        if size == 0:
            raise HTTPException(422, "The uploaded file is empty.")
        if not extraction.looks_like(file_type, head):
            raise HTTPException(422, f"This doesn't look like a real {suffix} file.")
        try:
            extracted = extraction.extract_text(path, file_type)
        except extraction.ExtractionError as exc:
            raise HTTPException(422, str(exc)) from exc
        if not extracted.text:
            raise HTTPException(
                422,
                "No text could be extracted. If this is a scanned document or images only, "
                "it needs OCR first (not supported yet).",
            )
    except BaseException:
        path.unlink(missing_ok=True)
        raise

    cur = db.execute(
        """INSERT INTO documents
           (class_id, original_name, stored_name, file_type, size_bytes, page_count, extracted_text)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (class_id, original_name, stored_name, file_type, size, extracted.page_count, extracted.text),
    )
    db.commit()
    return get_document(cur.lastrowid, db)


@router.get("/documents/{document_id}", response_model=DocumentDetail)
def get_document(document_id: int, db: Db = Depends(get_db)):
    row = _document_row(db, document_id)
    data = {k: row[k] for k in DocumentSummary.model_fields}
    return DocumentDetail(
        **data,
        text=row["extracted_text"],
        summary=_summary_for(db, document_id),
        quiz=_latest_quiz(db, document_id),
    )


@router.get("/documents/{document_id}/file")
def download_document(document_id: int, db: Db = Depends(get_db)):
    row = _document_row(db, document_id)
    path = _stored_path(row["stored_name"])
    if not path.exists():
        raise HTTPException(404, "The stored file is missing from disk.")
    return FileResponse(path, filename=row["original_name"])


@router.delete("/documents/{document_id}", status_code=204)
def delete_document(document_id: int, db: Db = Depends(get_db)):
    row = _document_row(db, document_id)
    db.execute("DELETE FROM documents WHERE id = ?", (document_id,))
    db.commit()
    _remove_files([row["stored_name"]])


# --------------------------------------------------------------------------- #
# Summaries and quizzes
# --------------------------------------------------------------------------- #


@router.post("/documents/{document_id}/summary", response_model=SummaryOut)
def create_summary(document_id: int, db: Db = Depends(get_db)):
    """Generate (or regenerate) the summary for a document."""
    text = _document_row(db, document_id)["extracted_text"]
    result = _llm_call(llm.summarize, text)
    model = config.ollama_model()
    db.execute(
        """INSERT INTO summaries (document_id, overview, key_points_json, model)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(document_id) DO UPDATE SET
             overview = excluded.overview, key_points_json = excluded.key_points_json,
             model = excluded.model,
             created_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')""",
        (document_id, result.overview.strip(), json.dumps([p.strip() for p in result.key_points]), model),
    )
    db.commit()
    return _summary_for(db, document_id)


@router.post("/documents/{document_id}/quiz", response_model=QuizOut, status_code=201)
def create_quiz(document_id: int, payload: QuizRequest | None = None, db: Db = Depends(get_db)):
    """Generate a new quiz and grade every question against the source text."""
    payload = payload or QuizRequest()
    text = _document_row(db, document_id)["extracted_text"]
    questions = _llm_call(llm.generate_quiz, text, payload.num_questions)

    cur = db.execute(
        "INSERT INTO quizzes (document_id, model) VALUES (?, ?)", (document_id, config.ollama_model())
    )
    quiz_id = cur.lastrowid
    db.executemany(
        """INSERT INTO quiz_questions
           (quiz_id, position, question, choices_json, answer_index, explanation, source_quote,
            quote_match, grounding_score, grounding_verdict, grounding_notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            (quiz_id, i, q.question, json.dumps(q.choices), q.answer_index, q.explanation,
             q.source_quote, q.quote_match, q.grounding_score, q.grounding_verdict, q.grounding_notes)
            for i, q in enumerate(questions)
        ],
    )
    db.commit()
    return _quiz_by_id(db, quiz_id)
