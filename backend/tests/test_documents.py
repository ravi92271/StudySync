import os

from .conftest import PHOTOSYNTHESIS, make_docx, make_pdf, make_pptx


def upload(client, class_id, name, data, content_type="application/octet-stream"):
    return client.post(f"/classes/{class_id}/documents", files={"file": (name, data, content_type)})


def test_classes_crud_and_duplicates(client):
    assert client.get("/classes").json() == []
    r = client.post("/classes", json={"name": "  Chemistry "})
    assert r.status_code == 201 and r.json()["name"] == "Chemistry"
    assert client.post("/classes", json={"name": "chemistry"}).status_code == 409  # case-insensitive
    assert client.post("/classes", json={"name": "   "}).status_code == 422
    assert client.get("/classes").json()[0]["document_count"] == 0


def test_upload_pdf_extracts_text_and_persists(client, class_id, tmp_path):
    r = upload(client, class_id, "notes.pdf", make_pdf())
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["original_name"] == "notes.pdf" and body["file_type"] == "pdf"
    assert body["page_count"] == 1
    assert "chlorophyll" in body["text"] and body["char_count"] == len(body["text"])
    assert body["summary"] is None and body["quiz"] is None

    # File is on disk under a random name, and the row is in SQLite.
    files = list((tmp_path / "data" / "uploads").iterdir())
    assert len(files) == 1 and files[0].name != "notes.pdf"
    assert (tmp_path / "data" / "studysync.db").exists()

    assert client.get(f"/classes/{class_id}/documents").json()[0]["id"] == body["id"]
    assert client.get("/classes").json()[0]["document_count"] == 1
    download = client.get(f"/documents/{body['id']}/file")
    assert download.status_code == 200 and download.content.startswith(b"%PDF")


def test_upload_docx_includes_table(client, class_id):
    body = upload(client, class_id, "notes.docx", make_docx()).json()
    assert "Biology notes" in body["text"] and "Organelle | Chloroplast" in body["text"]


def test_upload_pptx_includes_slides_and_notes(client, class_id):
    body = upload(client, class_id, "deck.pptx", make_pptx()).json()
    assert body["page_count"] == 1
    assert "Photosynthesis" in body["text"] and "Notes: Mention the Calvin cycle." in body["text"]


def test_rejects_bad_uploads(client, class_id, tmp_path):
    assert upload(client, class_id, "a.txt", b"hello").status_code == 415
    assert upload(client, class_id, "a.doc", b"hello").status_code == 415
    assert upload(client, class_id, "empty.pdf", b"").status_code == 422
    assert upload(client, class_id, "fake.pdf", b"not a pdf at all").status_code == 422
    assert upload(client, class_id, "fake.docx", b"PK\x03\x04garbage").status_code == 422
    blank = make_pdf("")  # a page with no text, like a scan
    r = upload(client, class_id, "scan.pdf", blank)
    assert r.status_code == 422 and "No text" in r.json()["detail"]
    assert client.post("/classes/999/documents", files={"file": ("a.pdf", make_pdf())}).status_code == 404
    # Rejected uploads leave nothing behind.
    assert os.listdir(tmp_path / "data" / "uploads") == []
    assert client.get(f"/classes/{class_id}/documents").json() == []


def test_path_traversal_filename_is_harmless(client, class_id, tmp_path):
    r = upload(client, class_id, "../../evil.pdf", make_pdf())
    assert r.status_code == 201 and r.json()["original_name"] == "evil.pdf"
    assert not (tmp_path / "evil.pdf").exists()


def test_size_limit(client, class_id, monkeypatch):
    monkeypatch.setattr("app.config.MAX_UPLOAD_BYTES", 100)
    assert upload(client, class_id, "big.pdf", make_pdf()).status_code == 413


def test_delete_document_and_class_remove_files(client, class_id, tmp_path):
    doc = upload(client, class_id, "a.pdf", make_pdf()).json()
    upload(client, class_id, "b.docx", make_docx())
    uploads = tmp_path / "data" / "uploads"
    assert len(os.listdir(uploads)) == 2
    assert client.delete(f"/documents/{doc['id']}").status_code == 204
    assert len(os.listdir(uploads)) == 1
    assert client.delete(f"/classes/{class_id}").status_code == 204
    assert os.listdir(uploads) == []
    assert client.get(f"/documents/{doc['id']}").status_code == 404
