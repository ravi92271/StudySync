# StudySync

StudySync is a student project for organizing course materials and, eventually, generating study notes and practice quizzes from them. This repository contains a Next.js website (`frontend/`) and a Python FastAPI server (`backend/`). Both run on your own computer during development.

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

`npm ci` installs the exact JavaScript dependencies recorded in `package-lock.json`. Leave this terminal open too. Visit [http://localhost:3000](http://localhost:3000/) to see the website. Seeing the default Next.js page is expected for now.

Keep both terminals running while working on the project. Press **Ctrl+C** in each terminal to stop its server. The website and API currently run independently; seeing both pages does not yet mean uploads or quiz generation are implemented.

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

## Planned next steps

1. Add a PDF upload endpoint and a form on the website. FastAPI file uploads will need `uv add python-multipart` in `backend/`.
2. Extract text from the uploaded document and display it in the website. PDF, Word, and PowerPoint parsing packages are already in the backend dependency list.
3. Save class and document information in a local SQLite database (Python includes `sqlite3`), and keep uploaded files in a local folder. Ignore both local data and uploaded files in Git.
4. Generate summaries and quizzes and evaluate whether questions reflect their source material. LangChain and its Ollama integration are installed as Python dependencies, but a local Ollama model is **not** set up or called by the application yet.

## If something does not work

- **`uv`, `node`, or `npm` is not recognized:** Install the missing tool from the links above, then open a new terminal.
- **`npm ci` fails with a Node version error:** Update Node.js to a supported version (20.9 or newer).
- **`Address already in use` / a port is busy:** Stop the other server using that port with Ctrl+C, then rerun the command.
- **The backend works but the website still shows Next.js branding:** That is the current starter page, not a setup error.
- **Changes are not appearing:** Check that the corresponding terminal is still running and that you are editing files in the correct folder.
