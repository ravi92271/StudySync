"use client";

import { useState } from "react";
import type { Question, Quiz, Verdict } from "../lib/api";

const VERDICT_STYLES: Record<Verdict, { label: string; className: string }> = {
  supported: {
    label: "Matches source",
    className: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300",
  },
  weak: {
    label: "Check this one",
    className: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300",
  },
  unsupported: {
    label: "Not supported by source",
    className: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300",
  },
};

function QuestionCard({ question, number }: { question: Question; number: number }) {
  const [picked, setPicked] = useState<number | null>(null);
  const verdict = VERDICT_STYLES[question.grounding_verdict];
  const answered = picked !== null;

  return (
    <li className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
      <div className="mb-3 flex items-start justify-between gap-3">
        <p className="font-medium">
          {number}. {question.question}
        </p>
        <span className={`shrink-0 rounded-full px-2.5 py-0.5 text-xs font-medium ${verdict.className}`}>
          {verdict.label}
        </span>
      </div>

      <div className="grid gap-2">
        {question.choices.map((choice, i) => {
          const isAnswer = i === question.answer_index;
          const state = !answered
            ? "border-zinc-300 hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-900"
            : isAnswer
              ? "border-emerald-500 bg-emerald-50 dark:bg-emerald-950"
              : i === picked
                ? "border-red-500 bg-red-50 dark:bg-red-950"
                : "border-zinc-200 opacity-60 dark:border-zinc-800";
          return (
            <button
              key={i}
              type="button"
              disabled={answered}
              onClick={() => setPicked(i)}
              className={`rounded-md border px-3 py-2 text-left text-sm transition-colors ${state}`}
            >
              <span className="mr-2 font-mono text-xs text-zinc-500">{"ABCDEF"[i]}</span>
              {choice}
            </button>
          );
        })}
      </div>

      {answered && (
        <p className="mt-3 text-sm">
          <strong>{picked === question.answer_index ? "Correct. " : "Not quite. "}</strong>
          {question.explanation}
        </p>
      )}

      <details className="mt-3 text-sm text-zinc-600 dark:text-zinc-400">
        <summary className="cursor-pointer select-none">
          Source check · score {Math.round(question.grounding_score * 100)}%
        </summary>
        <blockquote className="mt-2 border-l-2 border-zinc-300 pl-3 italic dark:border-zinc-700">
          {question.source_quote}
        </blockquote>
        <p className="mt-2">{question.grounding_notes}</p>
      </details>
    </li>
  );
}

export default function QuizView({ quiz }: { quiz: Quiz }) {
  const supported = quiz.questions.filter((q) => q.grounding_verdict === "supported").length;
  return (
    <div>
      <p className="mb-4 text-sm text-zinc-600 dark:text-zinc-400">
        {supported} of {quiz.questions.length} questions were verified against the source text. Generated with{" "}
        {quiz.model}. Questions marked &ldquo;Check this one&rdquo; or &ldquo;Not supported&rdquo; may be wrong,
        so verify them against your notes.
      </p>
      <ol className="grid gap-4">
        {quiz.questions.map((q, i) => (
          <QuestionCard key={q.id} question={q} number={i + 1} />
        ))}
      </ol>
    </div>
  );
}
