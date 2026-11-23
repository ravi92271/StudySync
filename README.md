# StudySync

StudySync is a student project for organizing course materials and generating study summaries and practice quizzes from them, using an AI model that runs on your own computer. This repository contains a Next.js website (`frontend/`) and a Python FastAPI server (`backend/`). Both run on your own computer during development.

## Before you start

Install these tools once on your computer:

1. **Git** to download the project: [git-scm.com/downloads](https://git-scm.com/downloads).
2. **Node.js** (version 20.9 or newer; choose the LTS release) for the website: [nodejs.org/en/download](https://nodejs.org/en/download). `npm` is installed with Node.js.
3. **uv** for the Python backend: [installation instructions](https://docs.astral.sh/uv/getting-started/installation/). You do not have to install Python separately: uv can download the Python version specified in `backend/.python-version`.

A **terminal** is the app where you type the commands below (Terminal on macOS, or PowerShell on Windows). Open a new terminal after installing tools so it recognizes them. To check that installation worked, run each command separately:

```bash
git --version
node --version
npm --version
uv --version
```

If a command says it was not found, revisit that tool's installation instructions before continuing.

## Get the code

If you already have the `StudySync` folder, open a terminal in that folder and skip the download command. Otherwise, copy the repository URL from your team's Git hosting page and run:

```bash
git clone <repository-url> StudySync
cd StudySync
```

Replace `<repository-url>` with the actual URL; do not type the angle brackets. In the examples below, commands marked `backend/` or `frontend/` should be run **inside that folder**, not in the top-level `StudySync` folder. `cd` means “change directory.”

## Start the backend (terminal 1)

From the `StudySync` folder:

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload
```

`uv sync` installs the project's Python version and the dependencies listed in `pyproject.toml`, using `uv.lock`. The first run may take a while. `uv run` uses the project's local Python environment; you do not need to activate it manually. `--reload` restarts the server when backend code changes.

Leave this terminal open. Visit [http://127.0.0.1:8000/](http://127.0.0.1:8000/) to see `{"message":"Hello World"}`. Visit [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) for FastAPI's interactive API documentation.

The backend entry point is `backend/app/main.py`. The separate `backend/main.py` is a starter file and does not start the API.

## Start the frontend (terminal 2)

Open a **second** terminal, go to the `StudySync` folder, and run:

```bash
cd frontend
npm ci
npm run dev
```

`npm ci` installs the exact JavaScript dependencies recorded in `package-lock.json`. Leave this terminal open too. Visit [http://localhost:3000](http://localhost:3000/) to see the website. It expects the backend (above) to be running on port 8000.

Keep both terminals running while working on the project. Press **Ctrl+C** in each terminal to stop its server. Uploading and reading documents works as soon as both servers are running. Summaries and quizzes additionally need Ollama (next section).

## Where things go

| Location | Purpose |
| --- | --- |
| `frontend/app/page.tsx` | Website's current home page |
| `frontend/app/layout.tsx` | Shared page layout and metadata |
| `backend/app/main.py` | FastAPI application and current API endpoint |
| `backend/pyproject.toml` | Python dependency list |
| `backend/uv.lock` | Locked Python dependency versions |
| `frontend/package.json` | Frontend scripts and dependency list |
| `frontend/package-lock.json` | Locked JavaScript dependency versions |

When adding a Python package, run `uv add <package-name>` **inside `backend/`**; for a frontend package, run `npm install <package-name>` **inside `frontend/`**. Commit changes to the relevant dependency file **and** lockfile so teammates install the same packages. Do not commit `backend/.venv/`, `frontend/node_modules/`, or generated local data.

## Using StudySync

1. Add a **class** in the left sidebar (for example "Biology 101").
2. Use the upload form to add a **PDF, Word (.docx) or PowerPoint (.pptx)** file (up to 25 MB). The text is extracted and shown in the **Extracted text** tab. Older `.doc`/`.ppt` files must be re-saved in the newer format, and scanned PDFs (images only) are rejected because there is no OCR yet.
3. Open the **Summary** or **Quiz** tab and press Generate.

Classes and documents are saved in a local SQLite database, and the uploaded files are kept in a local folder. Both live in `backend/data/`, which Git ignores. Delete that folder to start fresh. Set `STUDYSYNC_DATA_DIR` to store the data somewhere else.

## Set up Ollama (needed for summaries and quizzes)

Summaries and quizzes are written by a language model running locally through [Ollama](https://ollama.com), so your course material never leaves your computer.

1. Install Ollama from [ollama.com/download](https://ollama.com/download) and make sure it is running.
2. Download a model once: `ollama pull llama3.2`
3. Reload the website. A yellow banner appears at the top whenever Ollama isn't reachable or the model isn't downloaded, and tells you what to do.

To use a different model or server, set `STUDYSYNC_OLLAMA_MODEL` (default `llama3.2`) or `STUDYSYNC_OLLAMA_URL` (default `http://localhost:11434`) before starting the backend. Larger models write better questions but are slower. Generation on a laptop can take from several seconds to a few minutes.

### How quiz questions are checked against the source

Small local models sometimes invent facts, so every generated question is checked, and the result is shown as a badge on the question. Open **Source check** on a question to see the evidence.

- **Evidence quote.** The model must quote the sentence from your document that answers the question. StudySync measures how much of that quote really appears, word for word, in the passage the question was written from.
- **Independent read.** A second model call sees the passage and the question with the answer key *hidden* and picks an answer, or says the passage doesn't contain one. If it agrees with the key, the question is answerable from your material.

| Badge | Meaning |
| --- | --- |
| **Matches source** | The quote is in the document and the independent read agrees with the answer key. |
| **Check this one** | The quote is in the document, but the independent read disagreed or couldn't decide, so the question or its answer key may be flawed. |
| **Not supported by source** | The quoted evidence is not in the document. The question is probably invented. |

This is a safety net, not a guarantee: the same small model does the checking, so verify anything important against your notes.

## API

With the backend running, [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) lists every endpoint. The main ones:

| Endpoint | Purpose |
| --- | --- |
| `GET/POST /classes`, `DELETE /classes/{id}` | List, create and delete classes |
| `GET /classes/{id}/documents` | List a class's documents |
| `POST /classes/{id}/documents` | Upload a PDF, DOCX or PPTX (multipart form field `file`) |
| `GET /documents/{id}` | Document with extracted text, summary and latest quiz |
| `GET /documents/{id}/file`, `DELETE /documents/{id}` | Download the original, delete a document |
| `POST /documents/{id}/summary` | Generate a summary |
| `POST /documents/{id}/quiz` | Generate a graded quiz (`{"num_questions": 5}`) |
| `GET /llm/status` | Is Ollama reachable and is the model downloaded? |

### Run the backend tests

```
cd backend
uv run pytest
```

The tests use a fake model, so they run without Ollama.

## If something does not work

- **`uv`, `node`, or `npm` is not recognized:** Install the missing tool from the links above, then open a new terminal.
- **`npm ci` fails with a Node version error:** Update Node.js to a supported version (20.9 or newer).
- **`Address already in use` / a port is busy:** Stop the other server using that port with Ctrl+C, then rerun the command.
- **The website says it can't reach the backend:** Start the backend (terminal 1). If it runs on a different address, set `NEXT_PUBLIC_API_URL` before `npm run dev`.
- **"Could not reach Ollama" or "model is not downloaded":** Install and start Ollama, then run `ollama pull llama3.2` (see above).
- **"No text could be extracted":** The file is probably a scan or images only. Use a version with selectable text.
- **Changes are not appearing:** Check that the corresponding terminal is still running and that you are editing files in the correct folder.
