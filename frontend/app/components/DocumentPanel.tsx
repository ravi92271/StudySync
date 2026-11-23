"use client";

import { useState } from "react";
import { api, type DocumentDetail } from "../lib/api";
import QuizView from "./QuizView";

type Tab = "text" | "summary" | "quiz";

const button =
  "rounded-md bg-zinc-900 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300";

export default function DocumentPanel({
  doc,
  onChange,
  onDelete,
}: {
  doc: DocumentDetail;
  onChange: (doc: DocumentDetail) => void;
  onDelete: () => void;
}) {
  const [tab, setTab] = useState<Tab>("text");
  const [busy, setBusy] = useState<"summary" | "quiz" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [numQuestions, setNumQuestions] = useState(5);

  async function run<T>(kind: "summary" | "quiz", job: () => Promise<T>, apply: (result: T) => DocumentDetail) {
    setBusy(kind);
    setError(null);
    try {
      onChange(apply(await job()));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setBusy(null);
    }
  }

  const size = doc.size_bytes < 1024 * 1024 ? `${Math.ceil(doc.size_bytes / 1024)} KB` : `${(doc.size_bytes / 1024 / 1024).toFixed(1)} MB`;
  const unit = doc.file_type === "pptx" ? "slide" : "page";
  const units = doc.page_count ? ` · ${doc.page_count} ${unit}${doc.page_count === 1 ? "" : "s"}` : "";

  return (
    <section className="rounded-xl border border-zinc-200 dark:border-zinc-800">
      <header className="flex flex-wrap items-start justify-between gap-3 border-b border-zinc-200 p-4 dark:border-zinc-800">
        <div className="min-w-0">
          <h2 className="truncate text-lg font-semibold">{doc.original_name}</h2>
          <p className="text-sm text-zinc-500">
            {doc.file_type.toUpperCase()} · {size}
            {units} · {doc.char_count.toLocaleString()} characters extracted
          </p>
        </div>
        <div className="flex gap-3 text-sm">
          <a className="underline" href={api.fileUrl(doc.id)}>
            Download original
          </a>
          <button
            className="text-red-600 underline"
            onClick={() => {
              if (confirm(`Delete "${doc.original_name}"?`)) onDelete();
            }}
          >
            Delete
          </button>
        </div>
      </header>

      <nav className="flex gap-1 border-b border-zinc-200 px-4 dark:border-zinc-800" role="tablist">
        {(["text", "summary", "quiz"] as const).map((t) => (
          <button
            key={t}
            role="tab"
            aria-selected={tab === t}
            onClick={() => setTab(t)}
            className={`-mb-px border-b-2 px-3 py-2 text-sm font-medium capitalize ${
              tab === t ? "border-zinc-900 dark:border-zinc-100" : "border-transparent text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200"
            }`}
          >
            {t === "text" ? "Extracted text" : t}
          </button>
        ))}
      </nav>

      <div className="p-4">
        {error && (
          <p role="alert" className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-800 dark:bg-red-950 dark:text-red-300">
            {error}
          </p>
        )}

        {tab === "text" && (
          <pre className="max-h-[32rem] overflow-auto whitespace-pre-wrap break-words rounded-md bg-zinc-50 p-4 font-sans text-sm leading-6 dark:bg-zinc-900">
            {doc.text}
          </pre>
        )}

        {tab === "summary" && (
          <div>
            <button
              className={button}
              disabled={busy !== null}
              onClick={() => run("summary", () => api.createSummary(doc.id), (summary) => ({ ...doc, summary }))}
            >
              {busy === "summary" ? "Summarizing… (can take a minute)" : doc.summary ? "Regenerate summary" : "Generate summary"}
            </button>
            {doc.summary && (
              <div className="mt-4">
                <p className="leading-7">{doc.summary.overview}</p>
                <ul className="mt-3 list-disc space-y-1 pl-5">
                  {doc.summary.key_points.map((p, i) => (
                    <li key={i}>{p}</li>
                  ))}
                </ul>
                <p className="mt-4 text-xs text-zinc-500">Generated locally with {doc.summary.model}.</p>
              </div>
            )}
          </div>
        )}

        {tab === "quiz" && (
          <div>
            <div className="mb-4 flex flex-wrap items-center gap-3">
              <label className="text-sm">
                Questions{" "}
                <select
                  className="rounded-md border border-zinc-300 bg-transparent px-2 py-1 dark:border-zinc-700"
                  value={numQuestions}
                  onChange={(e) => setNumQuestions(Number(e.target.value))}
                >
                  {[3, 5, 8, 10].map((n) => (
                    <option key={n} value={n} className="text-black">
                      {n}
                    </option>
                  ))}
                </select>
              </label>
              <button
                className={button}
                disabled={busy !== null}
                onClick={() => run("quiz", () => api.createQuiz(doc.id, numQuestions), (quiz) => ({ ...doc, quiz }))}
              >
                {busy === "quiz" ? "Writing and checking questions… (can take a few minutes)" : doc.quiz ? "Generate a new quiz" : "Generate quiz"}
              </button>
            </div>
            {doc.quiz && <QuizView key={doc.quiz.id} quiz={doc.quiz} />}
          </div>
        )}
      </div>
    </section>
  );
}
