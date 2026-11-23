"""Pull plain text out of PDF, Word (.docx) and PowerPoint (.pptx) files."""

import re
from dataclasses import dataclass
from pathlib import Path

import pymupdf
from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph
from pptx import Presentation
from pptx.shapes.group import GroupShape

# Extension -> short type name stored in the database.
SUPPORTED_TYPES = {".pdf": "pdf", ".docx": "docx", ".pptx": "pptx"}


class ExtractionError(Exception):
    """The file could not be read as the type its extension claims."""


@dataclass
class Extracted:
    text: str
    page_count: int | None  # pages (PDF) or slides (PPTX); unknown for DOCX


def clean_text(text: str) -> str:
    text = text.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def looks_like(file_type: str, head: bytes) -> bool:
    """Cheap check that file contents match the extension (not just the name)."""
    if file_type == "pdf":
        return head.lstrip().startswith(b"%PDF")
    return head.startswith(b"PK")  # .docx and .pptx are zip archives


def extract_pdf(path: Path) -> Extracted:
    try:
        with pymupdf.open(path) as doc:
            if doc.needs_pass:
                raise ExtractionError("This PDF is password-protected.")
            pages = []
            for page in doc:
                # Text blocks (type 0), in reading order, separated by blank lines.
                blocks = page.get_text("blocks", sort=True)
                pages.append("\n\n".join(b[4].strip() for b in blocks if b[6] == 0 and b[4].strip()))
            return Extracted(clean_text("\n\n".join(pages)), doc.page_count)
    except ExtractionError:
        raise
    except Exception as exc:
        raise ExtractionError(f"Could not read this PDF: {exc}") from exc


def extract_docx(path: Path) -> Extracted:
    try:
        doc = Document(str(path))
        parts: list[str] = []
        # Walk the body in order so tables stay between the paragraphs around them.
        for child in doc.element.body.iterchildren():
            if child.tag.endswith("}p"):
                parts.append(Paragraph(child, doc).text.strip())
            elif child.tag.endswith("}tbl"):
                for row in Table(child, doc).rows:
                    cells, previous = [], None
                    for cell in row.cells:
                        if cell._tc is not previous:  # merged cells repeat
                            cells.append(cell.text.strip())
                        previous = cell._tc
                    parts.append(" | ".join(cells))
        return Extracted(clean_text("\n\n".join(p for p in parts if p)), None)
    except Exception as exc:
        raise ExtractionError(f"Could not read this Word document: {exc}") from exc


def _shape_texts(shape):
    if isinstance(shape, GroupShape):
        for inner in shape.shapes:
            yield from _shape_texts(inner)
    elif getattr(shape, "has_table", False) and shape.has_table:
        for row in shape.table.rows:
            yield " | ".join(c.text.strip() for c in row.cells)
    elif shape.has_text_frame:
        text = shape.text_frame.text.strip()
        if text:
            yield text


def extract_pptx(path: Path) -> Extracted:
    try:
        prs = Presentation(str(path))
        slides: list[str] = []
        for slide in prs.slides:
            lines = [t for shape in slide.shapes for t in _shape_texts(shape)]
            if slide.has_notes_slide:
                notes = slide.notes_slide.notes_text_frame.text.strip()
                if notes:
                    lines.append(f"Notes: {notes}")
            if lines:
                slides.append("\n".join(lines))
        return Extracted(clean_text("\n\n".join(slides)), len(prs.slides))
    except Exception as exc:
        raise ExtractionError(f"Could not read this PowerPoint file: {exc}") from exc


EXTRACTORS = {"pdf": extract_pdf, "docx": extract_docx, "pptx": extract_pptx}


def extract_text(path: Path, file_type: str) -> Extracted:
    return EXTRACTORS[file_type](path)
