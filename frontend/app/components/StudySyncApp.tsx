"use client";

import { useEffect, useRef, useState } from "react";
import { api, type ClassItem, type DocumentDetail, type DocumentItem, type LLMStatus } from "../lib/api";
import DocumentPanel from "./DocumentPanel";

const input =
  "rounded-md border border-zinc-300 bg-transparent px-3 py-1.5 text-sm dark:border-zinc-700";
const primary =
  "rounded-md bg-zinc-900 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300";

export default function StudySyncApp() {
  const [classes, setClasses] = useState<ClassItem[]>([]);
  const [classId, setClassId] = useState<number | null>(null);
  const [docs, setDocs] = useState<DocumentItem[]>([]);
  const [doc, setDoc] = useState<DocumentDetail | null>(null);
  const [llm, setLlm] = useState<LLMStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [newClass, setNewClass] = useState("");
  const [uploading, setUploading] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  const selectedClass = classes.find((c) => c.id === classId) ?? null;

  /** Run an action, showing any error in the page instead of crashing. */
  async function attempt(action: () => Promise<void>) {
    setError(null);
    try {
      await action();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    }
  }

  async function refreshClasses(): Promise<ClassItem[]> {
    const list = await api.listClasses();
    setClasses(list);
    return list;
  }

  async function openClass(id: number | null) {
    setClassId(id);
    setDoc(null);
    setDocs(id === null ? [] : await api.listDocuments(id));
  }

  // Load classes and the Ollama status once, when the page opens.
  useEffect(() => {
    (async () => {
      try {
        const list = await api.listClasses();
        setClasses(list);
        if (list.length > 0) await openClass(list[0].id);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Something went wrong.");
      }
    })();
    api.llmStatus().then(setLlm).catch(() => {});
  }, []);

  function addClass(e: React.FormEvent) {
    e.preventDefault();
    const name = newClass.trim();
    if (!name) return;
    attempt(async () => {
      const created = await api.createClass(name);
      setNewClass("");
      await refreshClasses();
      await openClass(created.id);
    });
  }

  function removeClass(c: ClassItem) {
    if (!confirm(`Delete "${c.name}" and all ${c.document_count} of its documents?`)) return;
    attempt(async () => {
      await api.deleteClass(c.id);
      const list = await refreshClasses();
      await openClass(list[0]?.id ?? null);
    });
  }

  function upload(e: React.FormEvent) {
    e.preventDefault();
    const file = fileInput.current?.files?.[0];
    if (!file || classId === null) return;
    setUploading(true);
    attempt(async () => {
      const created = await api.uploadDocument(classId, file);
      if (fileInput.current) fileInput.current.value = "";
      setDoc(created);
      setDocs(await api.listDocuments(classId));
      await refreshClasses();
    }).finally(() => setUploading(false));
  }

  function openDocument(id: number) {
    attempt(async () => setDoc(await api.getDocument(id)));
  }

  function removeDocument(id: number) {
    attempt(async () => {
      await api.deleteDocument(id);
      setDoc(null);
      if (classId !== null) setDocs(await api.listDocuments(classId));
      await refreshClasses();
    });
  }

  const llmProblem = llm && (!llm.reachable || !llm.model_available) ? llm.hint : null;

  return (
    <div className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 sm:px-6">
      <header className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight">StudySync</h1>
        <p className="text-sm text-zinc-500">
          Upload course materials, then generate summaries and quizzes with a model running on your computer.
        </p>
      </header>

      {error && (
        <p role="alert" className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-800 dark:bg-red-950 dark:text-red-300">
          {error}
        </p>
      )}
      {llmProblem && (
        <p className="mb-4 rounded-md bg-amber-50 p-3 text-sm text-amber-900 dark:bg-amber-950 dark:text-amber-200">
          Summaries and quizzes need a local Ollama model. {llmProblem} You can still upload documents and read
          their text.
        </p>
      )}

      <div className="grid gap-6 md:grid-cols-[16rem_1fr]">
        <aside>
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-zinc-500">Classes</h2>
          <ul className="mb-3 grid gap-1">
            {classes.map((c) => (
              <li key={c.id} className="group flex items-center gap-1">
                <button
                  onClick={() => attempt(() => openClass(c.id))}
                  aria-current={c.id === classId}
                  className={`flex-1 truncate rounded-md px-3 py-2 text-left text-sm ${
                    c.id === classId ? "bg-zinc-200 font-medium dark:bg-zinc-800" : "hover:bg-zinc-100 dark:hover:bg-zinc-900"
                  }`}
                >
                  {c.name} <span className="text-zinc-500">({c.document_count})</span>
                </button>
                <button
                  aria-label={`Delete ${c.name}`}
                  onClick={() => removeClass(c)}
                  className="px-2 text-zinc-400 hover:text-red-600"
                >
                  ×
                </button>
              </li>
            ))}
            {classes.length === 0 && <li className="text-sm text-zinc-500">No classes yet. Add your first one below.</li>}
          </ul>
          <form onSubmit={addClass} className="flex gap-2">
            <input
              className={`${input} min-w-0 flex-1`}
              placeholder="New class name"
              maxLength={120}
              value={newClass}
              onChange={(e) => setNewClass(e.target.value)}
            />
            <button className={primary} disabled={!newClass.trim()}>
              Add
            </button>
          </form>
        </aside>

        <main className="grid min-w-0 content-start gap-6">
          {!selectedClass ? (
            <p className="text-zinc-500">Create a class to start uploading materials.</p>
          ) : (
            <>
              <section>
                <h2 className="mb-3 text-lg font-semibold">{selectedClass.name}</h2>
                <form onSubmit={upload} className="flex flex-wrap items-center gap-3">
                  <input
                    ref={fileInput}
                    type="file"
                    accept=".pdf,.docx,.pptx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.openxmlformats-officedocument.presentationml.presentation"
                    required
                    aria-label="Document to upload"
                    className="text-sm file:mr-3 file:rounded-md file:border file:border-zinc-300 file:bg-transparent file:px-3 file:py-1.5 file:text-sm dark:file:border-zinc-700"
                  />
                  <button className={primary} disabled={uploading}>
                    {uploading ? "Uploading…" : "Upload"}
                  </button>
                  <span className="text-xs text-zinc-500">PDF, Word (.docx) or PowerPoint (.pptx), up to 25 MB</span>
                </form>

                <ul className="mt-4 grid gap-1">
                  {docs.map((d) => (
                    <li key={d.id}>
                      <button
                        onClick={() => openDocument(d.id)}
                        aria-current={doc?.id === d.id}
                        className={`flex w-full items-center justify-between gap-3 rounded-md border px-3 py-2 text-left text-sm ${
                          doc?.id === d.id
                            ? "border-zinc-400 bg-zinc-100 dark:border-zinc-600 dark:bg-zinc-900"
                            : "border-zinc-200 hover:bg-zinc-50 dark:border-zinc-800 dark:hover:bg-zinc-900"
                        }`}
                      >
                        <span className="truncate">{d.original_name}</span>
                        <span className="shrink-0 text-xs uppercase text-zinc-500">{d.file_type}</span>
                      </button>
                    </li>
                  ))}
                  {docs.length === 0 && <li className="text-sm text-zinc-500">No documents in this class yet.</li>}
                </ul>
              </section>

              {doc && (
                <DocumentPanel
                  key={doc.id}
                  doc={doc}
                  onChange={setDoc}
                  onDelete={() => removeDocument(doc.id)}
                />
              )}
            </>
          )}
        </main>
      </div>
    </div>
  );
}
