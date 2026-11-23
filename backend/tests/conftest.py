import io

import pymupdf
import pytest
from docx import Document
from fastapi.testclient import TestClient
from pptx import Presentation

from app.main import app

PHOTOSYNTHESIS = (
    "Photosynthesis is the process by which plants convert light energy into chemical energy. "
    "It takes place in the chloroplasts, which contain the green pigment chlorophyll. "
    "The light reactions occur in the thylakoid membranes and produce ATP and NADPH. "
    "The Calvin cycle then uses ATP and NADPH to fix carbon dioxide into glucose in the stroma."
)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDYSYNC_DATA_DIR", str(tmp_path / "data"))
    with TestClient(app) as c:  # the context manager runs startup (creates the DB)
        yield c


def make_pdf(text: str = PHOTOSYNTHESIS) -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_textbox(pymupdf.Rect(50, 50, 550, 700), text)
    data = doc.tobytes()
    doc.close()
    return data


def make_docx(text: str = PHOTOSYNTHESIS) -> bytes:
    doc = Document()
    doc.add_heading("Biology notes", 1)
    doc.add_paragraph(text)
    table = doc.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = "Organelle"
    table.rows[0].cells[1].text = "Chloroplast"
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def make_pptx(text: str = PHOTOSYNTHESIS) -> bytes:
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[1])
    slide.shapes.title.text = "Photosynthesis"
    slide.placeholders[1].text = text
    slide.notes_slide.notes_text_frame.text = "Mention the Calvin cycle."
    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


@pytest.fixture
def class_id(client):
    return client.post("/classes", json={"name": "Biology 101"}).json()["id"]
