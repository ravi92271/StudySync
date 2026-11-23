"""Summaries, quizzes and quiz-quality checks using a local Ollama model via LangChain.

Nothing here talks to a cloud service: `ChatOllama` calls the Ollama server running
on your own computer (default http://localhost:11434).

Grounding ("do the questions reflect the source material?") is checked in two
independent ways for every generated question:

1. Quote check (no AI): the question must include a `source_quote`. We measure how
   much of that quote really appears, word for word, in the source passage.
2. Blind-solve check (AI): a second model call sees the passage and the question
   with the answer key hidden, and picks an answer, or says the passage doesn't
   contain the answer. If it agrees with the key, the question is answerable from
   the source and the key is right.

Verdicts: "supported" = quote found and the blind reader agrees with the key;
"unsupported" = the quoted evidence is not in the source; "weak" = the evidence is
there but the blind reader disagreed or couldn't answer, so the question or its key
may be flawed and a human should look.
"""

import random
import re
from dataclasses import dataclass
from difflib import SequenceMatcher

import httpx
import ollama
from langchain_ollama import ChatOllama
from pydantic import BaseModel, Field, ValidationError

from . import config

# Rough sizes in characters (about 4 characters per token).
SUMMARY_CHUNK_CHARS = 8000
QUIZ_CHUNK_CHARS = 3500
MIN_QUIZ_CHUNK_CHARS = 300
MAX_QUIZ_ATTEMPTS = 2

QUOTE_EXACT = 0.9  # quote_match at or above this counts as "found in the source"
QUOTE_MISSING = 0.5  # below this the quote is basically not in the source


class LLMUnavailable(Exception):
    """Ollama isn't running, or the configured model hasn't been downloaded."""


class LLMOutputError(Exception):
    """The model kept returning output we couldn't use."""


# --------------------------------------------------------------------------- #
# Model access
# --------------------------------------------------------------------------- #


def get_chat_model(temperature: float = 0.2):
    """Create the chat model. Tests replace this function with a fake."""
    return ChatOllama(
        model=config.ollama_model(),
        base_url=config.ollama_base_url(),
        temperature=temperature,
        num_ctx=8192,  # room for a chunk plus the prompt and the answer
    )


def _ask(schema: type[BaseModel], system: str, user: str, temperature: float):
    """Call the model and get back a validated `schema` object."""
    runnable = get_chat_model(temperature).with_structured_output(schema)
    try:
        result = runnable.invoke([("system", system), ("human", user)])
    except (ConnectionError, httpx.ConnectError) as exc:
        raise LLMUnavailable(
            f"Could not reach Ollama at {config.ollama_base_url()}. "
            "Install it from https://ollama.com and make sure it is running."
        ) from exc
    except ollama.ResponseError as exc:
        if exc.status_code == 404:
            raise LLMUnavailable(
                f"The model '{config.ollama_model()}' is not downloaded. "
                f"Run: ollama pull {config.ollama_model()}"
            ) from exc
        raise LLMOutputError(f"Ollama returned an error: {exc}") from exc
    except (ValidationError, ValueError) as exc:
        raise LLMOutputError(f"The model returned malformed output: {exc}") from exc
    if isinstance(result, dict):
        try:
            result = schema.model_validate(result)
        except ValidationError as exc:
            raise LLMOutputError(f"The model returned malformed output: {exc}") from exc
    if not isinstance(result, schema):
        raise LLMOutputError("The model returned no structured output.")
    return result


def status() -> dict:
    """Is Ollama reachable, and is the configured model downloaded?"""
    model = config.ollama_model()
    info = {
        "reachable": False,
        "model": model,
        "model_available": False,
        "installed_models": [],
        "hint": None,
    }
    try:
        listing = ollama.Client(host=config.ollama_base_url()).list()
    except Exception:
        info["hint"] = (
            f"Ollama is not reachable at {config.ollama_base_url()}. "
            "Install it from https://ollama.com and start it."
        )
        return info
    names = [m.model for m in listing.models if m.model]
    wanted = model if ":" in model else f"{model}:latest"
    info.update(reachable=True, installed_models=names, model_available=wanted in names)
    if not info["model_available"]:
        info["hint"] = f"Download the model with: ollama pull {model}"
    return info


# --------------------------------------------------------------------------- #
# Text splitting
# --------------------------------------------------------------------------- #


def _hard_split(piece: str, max_chars: int) -> list[str]:
    """Split one over-long paragraph on sentence ends, then on length."""
    if len(piece) <= max_chars:
        return [piece]
    out, current = [], ""
    for sentence in re.split(r"(?<=[.!?])\s+", piece):
        while len(sentence) > max_chars:  # no punctuation at all: cut blindly
            if current:
                out.append(current)
                current = ""
            out.append(sentence[:max_chars])
            sentence = sentence[max_chars:]
        if current and len(current) + 1 + len(sentence) > max_chars:
            out.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        out.append(current)
    return out


def split_text(text: str, max_chars: int) -> list[str]:
    """Pack paragraphs into chunks of at most `max_chars` characters."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks, current = [], ""
    for paragraph in paragraphs:
        for piece in _hard_split(paragraph, max_chars):
            if current and len(current) + 2 + len(piece) > max_chars:
                chunks.append(current)
                current = piece
            else:
                current = f"{current}\n\n{piece}" if current else piece
    if current:
        chunks.append(current)
    return chunks


# --------------------------------------------------------------------------- #
# Summaries
# --------------------------------------------------------------------------- #


class SummaryOut(BaseModel):
    overview: str = Field(description="2-4 sentence overview of the material")
    key_points: list[str] = Field(description="The most important facts, terms or ideas, one per item")


SUMMARY_SYSTEM = (
    "You are a study assistant helping a student review course material. "
    "Summarize faithfully using ONLY the text provided. Never add outside facts. "
    "Prefer concrete details (terms, definitions, names, numbers) over vague statements."
)


def _summarize_once(text: str, what: str) -> SummaryOut:
    return _ask(
        SummaryOut,
        SUMMARY_SYSTEM,
        f"Summarize {what}. Give a short overview and 5-8 key points.\n\n---\n{text}\n---",
        temperature=0.2,
    )


def _render(summary: SummaryOut) -> str:
    bullets = "\n".join(f"- {p}" for p in summary.key_points)
    return f"{summary.overview}\n{bullets}"


def summarize(text: str) -> SummaryOut:
    """Summarize a document, condensing in stages when it doesn't fit in one prompt."""
    chunks = split_text(text, SUMMARY_CHUNK_CHARS)
    if not chunks:
        raise LLMOutputError("There is no text to summarize.")
    if len(chunks) == 1:
        return _summarize_once(chunks[0], "the following material")

    # Long document: summarize each part, then summarize the summaries.
    parts = [_render(_summarize_once(c, f"part {i} of {len(chunks)} of a document"))
             for i, c in enumerate(chunks, 1)]
    while True:
        combined = "\n\n".join(parts)
        if len(combined) <= SUMMARY_CHUNK_CHARS or len(parts) == 1:
            return _summarize_once(combined, "the whole document, based on these part summaries")
        groups = split_text(combined, SUMMARY_CHUNK_CHARS)
        if len(groups) >= len(parts):  # can't shrink further
            return _summarize_once(combined[:SUMMARY_CHUNK_CHARS], "the whole document")
        parts = [_render(_summarize_once(g, "these part summaries")) for g in groups]


# --------------------------------------------------------------------------- #
# Quizzes
# --------------------------------------------------------------------------- #


class QuestionOut(BaseModel):
    question: str
    choices: list[str] = Field(description="Exactly 4 answer choices")
    answer_index: int = Field(description="0-based index of the correct choice")
    explanation: str = Field(description="One sentence on why the answer is correct")
    source_quote: str = Field(description="Sentence copied word for word from the passage that answers the question")


class QuizOut(BaseModel):
    questions: list[QuestionOut]


QUIZ_SYSTEM = (
    "You write multiple-choice study questions from course material. "
    "Use ONLY the passage you are given; never use outside knowledge. "
    "Each question tests one concrete fact or idea. It must not mention 'the passage' or 'the text'. "
    "Each question has exactly 4 choices: one correct and three plausible but clearly wrong "
    "according to the passage. 'answer_index' is the 0-based position of the correct choice. "
    "'source_quote' must be copied EXACTLY, word for word, from the passage (one or two sentences) "
    "and must contain the information needed to answer."
)


@dataclass
class GradedQuestion:
    question: str
    choices: list[str]
    answer_index: int
    explanation: str
    source_quote: str
    quote_match: float
    grounding_score: float
    grounding_verdict: str  # "supported" | "weak" | "unsupported"
    grounding_notes: str


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def quote_match_score(quote: str, passage: str) -> float:
    """0..1: how much of `quote` appears word for word in `passage`."""
    q, p = _normalize(quote), _normalize(passage)
    if not q or not p:
        return 0.0
    if q in p:
        return 1.0
    longest = SequenceMatcher(None, q, p, autojunk=False).find_longest_match(0, len(q), 0, len(p))
    return longest.size / len(q)


class BlindAnswer(BaseModel):
    reasoning: str = Field(description="Brief reasoning based only on the passage")
    answer_index: int = Field(
        description="0-based index of the choice the passage supports, or -1 if the passage does not contain the answer"
    )


BLIND_SYSTEM = (
    "You are checking a quiz question against its source passage. Answer using ONLY the passage. "
    "If the passage does not contain enough information to answer, or if more than one choice "
    "could be correct according to the passage, answer -1."
)


def evaluate_question(q: QuestionOut, passage: str) -> GradedQuestion:
    """Score how well a question reflects the passage it was written from."""
    quote_match = quote_match_score(q.source_quote, passage)

    numbered = "\n".join(f"{i}. {c}" for i, c in enumerate(q.choices))
    try:
        blind = _ask(
            BlindAnswer,
            BLIND_SYSTEM,
            f"Passage:\n---\n{passage}\n---\n\nQuestion: {q.question}\nChoices:\n{numbered}",
            temperature=0.0,
        )
        solved: int | None = blind.answer_index
        reasoning = blind.reasoning.strip()
    except LLMOutputError:
        solved, reasoning = None, ""  # fall back to the quote check alone

    notes: list[str] = []
    if quote_match >= QUOTE_EXACT:
        notes.append("The quoted evidence appears in the source.")
    elif quote_match >= QUOTE_MISSING:
        notes.append("The quoted evidence only partly matches the source.")
    else:
        notes.append("The quoted evidence was not found in the source.")

    if solved is None:
        notes.append("The independent answer check could not run.")
        verdict = "supported" if quote_match >= QUOTE_EXACT else "weak" if quote_match >= QUOTE_MISSING else "unsupported"
        score = quote_match * 0.5
    else:
        agrees = solved == q.answer_index
        if solved == -1:
            notes.append("An independent read of the source could not find a single clear answer.")
        elif agrees:
            notes.append("An independent read of the source reached the same answer.")
        else:
            notes.append("An independent read of the source chose a different answer.")
        if quote_match < QUOTE_MISSING or (solved == -1 and quote_match < QUOTE_EXACT):
            verdict = "unsupported"  # the evidence isn't really in the source
        elif quote_match >= QUOTE_EXACT and agrees:
            verdict = "supported"
        else:
            verdict = "weak"  # evidence exists, but the question or key may be flawed
        score = 0.5 * quote_match + 0.5 * (1.0 if agrees else 0.0)
    if reasoning:
        notes.append(f"Checker's reasoning: {reasoning}")

    return GradedQuestion(
        question=q.question,
        choices=q.choices,
        answer_index=q.answer_index,
        explanation=q.explanation,
        source_quote=q.source_quote,
        quote_match=round(quote_match, 3),
        grounding_score=round(score, 3),
        grounding_verdict=verdict,
        grounding_notes=" ".join(notes),
    )


def _clean_question(q: QuestionOut, rng: random.Random) -> QuestionOut | None:
    """Drop malformed questions; shuffle choices so the key isn't always in one slot."""
    choices = [c.strip() for c in q.choices if c and c.strip()]
    if not (2 <= len(choices) <= 6) or len({c.lower() for c in choices}) != len(choices):
        return None
    if len(choices) != len(q.choices) or not (0 <= q.answer_index < len(choices)):
        return None
    if not q.question.strip() or not q.source_quote.strip():
        return None
    order = list(range(len(choices)))
    rng.shuffle(order)
    return QuestionOut(
        question=q.question.strip(),
        choices=[choices[i] for i in order],
        answer_index=order.index(q.answer_index),
        explanation=q.explanation.strip(),
        source_quote=q.source_quote.strip(),
    )


def _pick_chunks(text: str, num_questions: int) -> list[tuple[str, int]]:
    """Choose passages spread across the document, with how many questions each gets."""
    chunks = [c for c in split_text(text, QUIZ_CHUNK_CHARS) if len(c) >= MIN_QUIZ_CHUNK_CHARS]
    if not chunks and text.strip():
        chunks = [text.strip()]
    if not chunks:
        return []
    count = min(num_questions, len(chunks))
    # Evenly spaced chunks so the whole document is covered, not just the start.
    picked = [chunks[int(i * len(chunks) / count)] for i in range(count)]
    base, extra = divmod(num_questions, count)
    return [(chunk, base + (1 if i < extra else 0)) for i, chunk in enumerate(picked)]


def generate_quiz(text: str, num_questions: int) -> list[GradedQuestion]:
    """Generate up to `num_questions` questions and grade each against its source passage."""
    plan = _pick_chunks(text, num_questions)
    if not plan:
        raise LLMOutputError("There is no text to build a quiz from.")

    rng = random.Random()
    graded: list[GradedQuestion] = []
    last_error: LLMOutputError | None = None
    for passage, wanted in plan:
        for _attempt in range(MAX_QUIZ_ATTEMPTS):
            try:
                out = _ask(
                    QuizOut,
                    QUIZ_SYSTEM,
                    f"Write {wanted} multiple-choice question{'s' if wanted != 1 else ''} "
                    f"from this passage.\n\nPassage:\n---\n{passage}\n---",
                    temperature=0.4,
                )
            except LLMOutputError as exc:
                last_error = exc
                continue
            questions = [c for c in (_clean_question(q, rng) for q in out.questions) if c]
            if questions:
                graded.extend(evaluate_question(q, passage) for q in questions[:wanted])
                break
    if not graded:
        raise last_error or LLMOutputError("The model did not produce any usable questions.")
    return graded[:num_questions]

