"""Request and response shapes for the API."""

from pydantic import BaseModel, Field


class ClassCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class ClassOut(BaseModel):
    id: int
    name: str
    created_at: str
    document_count: int


class DocumentSummary(BaseModel):
    """A document as shown in a list (no extracted text)."""

    id: int
    class_id: int
    original_name: str
    file_type: str
    size_bytes: int
    page_count: int | None
    char_count: int
    created_at: str


class SummaryOut(BaseModel):
    overview: str
    key_points: list[str]
    model: str
    created_at: str


class QuestionOut(BaseModel):
    id: int
    question: str
    choices: list[str]
    answer_index: int
    explanation: str
    source_quote: str
    quote_match: float
    grounding_score: float
    grounding_verdict: str  # supported | weak | unsupported
    grounding_notes: str


class QuizOut(BaseModel):
    id: int
    model: str
    created_at: str
    questions: list[QuestionOut]


class DocumentDetail(DocumentSummary):
    text: str
    summary: SummaryOut | None
    quiz: QuizOut | None  # the most recent quiz


class QuizRequest(BaseModel):
    num_questions: int = Field(default=5, ge=1, le=15)


class LLMStatus(BaseModel):
    reachable: bool
    model: str
    model_available: bool
    installed_models: list[str]
    hint: str | None
