"""Runtime settings. Everything can be overridden with environment variables."""

import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent

# Uploaded files may be at most this large.
MAX_UPLOAD_BYTES = 25 * 1024 * 1024

# Origins allowed to call the API from a browser (the Next.js dev server).
CORS_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]


def data_dir() -> Path:
    """Folder holding the SQLite database and uploaded files (ignored by Git)."""
    return Path(os.environ.get("STUDYSYNC_DATA_DIR", BACKEND_DIR / "data"))


def upload_dir() -> Path:
    return data_dir() / "uploads"


def db_path() -> Path:
    return data_dir() / "studysync.db"


def ollama_model() -> str:
    return os.environ.get("STUDYSYNC_OLLAMA_MODEL", "llama3.2")


def ollama_base_url() -> str:
    return os.environ.get("STUDYSYNC_OLLAMA_URL", "http://localhost:11434")
