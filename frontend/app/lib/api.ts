// Typed client for the StudySync FastAPI backend.

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export type ClassItem = {
  id: number;
  name: string;
  created_at: string;
  document_count: number;
};

export type DocumentItem = {
  id: number;
  class_id: number;
  original_name: string;
  file_type: "pdf" | "docx" | "pptx";
  size_bytes: number;
  page_count: number | null;
  char_count: number;
  created_at: string;
};

export type Summary = {
  overview: string;
  key_points: string[];
  model: string;
  created_at: string;
};

export type Verdict = "supported" | "weak" | "unsupported";

export type Question = {
  id: number;
  question: string;
  choices: string[];
  answer_index: number;
  explanation: string;
  source_quote: string;
  quote_match: number;
  grounding_score: number;
  grounding_verdict: Verdict;
  grounding_notes: string;
};

export type Quiz = {
  id: number;
  model: string;
  created_at: string;
  questions: Question[];
};

export type DocumentDetail = DocumentItem & {
  text: string;
  summary: Summary | null;
  quiz: Quiz | null;
};

export type LLMStatus = {
  reachable: boolean;
  model: string;
  model_available: boolean;
  installed_models: string[];
  hint: string | null;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, init);
  } catch {
    throw new Error(
      `Can't reach the StudySync backend at ${API_URL}. Is it running? (cd backend && uv run uvicorn app.main:app --reload)`,
    );
  }
  if (!response.ok) {
    let message = `Request failed (${response.status}).`;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") message = body.detail;
      else if (Array.isArray(body.detail)) message = body.detail.map((d: { msg: string }) => d.msg).join("; ");
    } catch {
      // keep the generic message
    }
    throw new Error(message);
  }
  return response.status === 204 ? (undefined as T) : ((await response.json()) as T);
}

const json = (method: string, body?: unknown): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: body === undefined ? undefined : JSON.stringify(body),
});

export const api = {
  llmStatus: () => request<LLMStatus>("/llm/status"),
  listClasses: () => request<ClassItem[]>("/classes"),
  createClass: (name: string) => request<ClassItem>("/classes", json("POST", { name })),
  deleteClass: (id: number) => request<void>(`/classes/${id}`, { method: "DELETE" }),
  listDocuments: (classId: number) => request<DocumentItem[]>(`/classes/${classId}/documents`),
  uploadDocument: (classId: number, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<DocumentDetail>(`/classes/${classId}/documents`, { method: "POST", body: form });
  },
  getDocument: (id: number) => request<DocumentDetail>(`/documents/${id}`),
  deleteDocument: (id: number) => request<void>(`/documents/${id}`, { method: "DELETE" }),
  fileUrl: (id: number) => `${API_URL}/documents/${id}/file`,
  createSummary: (id: number) => request<Summary>(`/documents/${id}/summary`, json("POST")),
  createQuiz: (id: number, numQuestions: number) =>
    request<Quiz>(`/documents/${id}/quiz`, json("POST", { num_questions: numQuestions })),
};
