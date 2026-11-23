import httpx
import ollama
import pytest
from langchain_core.runnables import RunnableLambda

from app import llm

from .conftest import PHOTOSYNTHESIS, make_pdf

GOOD_Q = llm.QuestionOut(
    question="Where does the Calvin cycle take place?",
    choices=["Thylakoid membrane", "Stroma", "Nucleus", "Cell wall"],
    answer_index=1,
    explanation="The Calvin cycle fixes carbon dioxide in the stroma.",
    source_quote="The Calvin cycle then uses ATP and NADPH to fix carbon dioxide into glucose in the stroma.",
)
# The quote is invented, so it can't be found in the source.
INVENTED_Q = llm.QuestionOut(
    question="Which scientist discovered photosynthesis in 1779?",
    choices=["Ingenhousz", "Darwin", "Mendel", "Pasteur"],
    answer_index=0,
    explanation="Jan Ingenhousz did.",
    source_quote="Jan Ingenhousz demonstrated in 1779 that plants need sunlight to purify air.",
)
# The quote is real, but the answer key contradicts it.
WRONG_KEY_Q = llm.QuestionOut(
    question="Where do the light reactions occur?",
    choices=["Stroma", "Thylakoid membranes", "Mitochondria", "Vacuole"],
    answer_index=0,  # wrong: should be 1
    explanation="Light reactions occur in the stroma.",
    source_quote="The light reactions occur in the thylakoid membranes and produce ATP and NADPH.",
)


class FakeChat:
    """Stands in for ChatOllama. `quiz` is what the 'model' writes; the blind
    solver answers correctly according to the passage (the source of truth)."""

    def __init__(self, quiz=(), solver=None):
        self.quiz, self.solver, self.calls = list(quiz), solver, []

    def with_structured_output(self, schema):
        def run(messages):
            self.calls.append(schema.__name__)
            user = messages[1][1]
            if schema is llm.SummaryOut:
                return llm.SummaryOut(overview="Plants make sugar from light.", key_points=["Chlorophyll", "Calvin cycle"])
            if schema is llm.QuizOut:
                return llm.QuizOut(questions=self.quiz)
            if schema is llm.BlindAnswer:
                return self.solver(user)
            raise AssertionError(schema)

        return RunnableLambda(run)


def passage_solver(user: str) -> llm.BlindAnswer:
    """Picks the choice that the passage supports, like a careful reader would."""
    question = user.split("Question:", 1)[1]  # look at the question, not the passage
    if "Calvin cycle take place" in question:
        return llm.BlindAnswer(reasoning="Stroma.", answer_index=_index_of(user, "Stroma"))
    if "light reactions occur" in question:
        return llm.BlindAnswer(reasoning="Thylakoid.", answer_index=_index_of(user, "Thylakoid membranes"))
    return llm.BlindAnswer(reasoning="Not in passage.", answer_index=-1)


def _index_of(user: str, choice: str) -> int:
    for line in user.splitlines():
        head, _, tail = line.partition(". ")
        if head.isdigit() and tail == choice:
            return int(head)
    raise AssertionError(choice)


@pytest.fixture
def use_model(monkeypatch):
    def install(fake):
        monkeypatch.setattr(llm, "get_chat_model", lambda temperature=0.2: fake)
        return fake

    return install


@pytest.fixture
def doc_id(client, class_id):
    r = client.post(f"/classes/{class_id}/documents", files={"file": ("n.pdf", make_pdf())})
    return r.json()["id"]


# --- pure helpers ----------------------------------------------------------- #


def test_quote_match_score():
    assert llm.quote_match_score("the CALVIN cycle,  then uses ATP", PHOTOSYNTHESIS) == 1.0  # case/punctuation-insensitive
    assert llm.quote_match_score(GOOD_Q.source_quote, PHOTOSYNTHESIS) == 1.0
    assert llm.quote_match_score(INVENTED_Q.source_quote, PHOTOSYNTHESIS) < 0.5
    assert 0.5 < llm.quote_match_score("the Calvin cycle uses ATP", PHOTOSYNTHESIS) < 1.0  # partial
    assert llm.quote_match_score("", PHOTOSYNTHESIS) == 0.0


def test_split_text_respects_limit_and_keeps_content():
    text = "\n\n".join(f"Paragraph {i}. " + "word " * 40 for i in range(30))
    chunks = llm.split_text(text, 500)
    assert all(len(c) <= 500 for c in chunks) and len(chunks) > 1
    assert "Paragraph 29." in chunks[-1]
    one_long = "A sentence here. " * 200  # single paragraph, no blank lines
    assert all(len(c) <= 500 for c in llm.split_text(one_long, 500))
    assert all(len(c) <= 100 for c in llm.split_text("x" * 1000, 100))  # no punctuation at all


# --- summaries ---------------------------------------------------------------- #


def test_summary_is_stored_and_returned_with_document(client, doc_id, use_model):
    use_model(FakeChat())
    r = client.post(f"/documents/{doc_id}/summary")
    assert r.status_code == 200
    assert r.json()["overview"].startswith("Plants make sugar") and r.json()["key_points"] == ["Chlorophyll", "Calvin cycle"]
    assert client.get(f"/documents/{doc_id}").json()["summary"]["key_points"][0] == "Chlorophyll"
    assert client.post(f"/documents/{doc_id}/summary").status_code == 200  # regenerate overwrites


def test_long_document_is_summarized_in_stages(monkeypatch, use_model):
    fake = use_model(FakeChat())
    text = "\n\n".join("Sentence about cells. " * 30 for _ in range(60))  # ~40k chars
    llm.summarize(text)
    assert fake.calls.count("SummaryOut") > 2  # several part summaries, then a final one


# --- quizzes and grounding ---------------------------------------------------- #


def test_quiz_questions_are_graded_against_the_source(client, doc_id, use_model):
    use_model(FakeChat(quiz=[GOOD_Q, INVENTED_Q, WRONG_KEY_Q], solver=passage_solver))
    r = client.post(f"/documents/{doc_id}/quiz", json={"num_questions": 3})
    assert r.status_code == 201, r.text
    by_q = {q["question"]: q for q in r.json()["questions"]}

    good = by_q[GOOD_Q.question]
    assert good["grounding_verdict"] == "supported" and good["grounding_score"] == 1.0
    assert good["choices"][good["answer_index"]] == "Stroma"  # key survives shuffling

    invented = by_q[INVENTED_Q.question]
    assert invented["grounding_verdict"] == "unsupported" and invented["quote_match"] < 0.5

    wrong = by_q[WRONG_KEY_Q.question]  # real quote, but the key disagrees with the source
    assert wrong["quote_match"] == 1.0 and wrong["grounding_verdict"] == "weak"
    assert "different answer" in wrong["grounding_notes"]

    # Stored: the latest quiz comes back with the document.
    again = client.get(f"/documents/{doc_id}").json()["quiz"]
    assert [q["question"] for q in again["questions"]] == [q["question"] for q in r.json()["questions"]]


def test_real_quote_but_unanswerable_is_weak_not_unsupported(client, doc_id, use_model):
    """If the evidence is verifiably in the source, don't claim the source doesn't support it."""
    use_model(FakeChat(quiz=[GOOD_Q], solver=lambda user: llm.BlindAnswer(reasoning="Unsure.", answer_index=-1)))
    q = client.post(f"/documents/{doc_id}/quiz", json={"num_questions": 1}).json()["questions"][0]
    assert q["quote_match"] == 1.0 and q["grounding_verdict"] == "weak"


def test_malformed_questions_are_dropped(client, doc_id, use_model):
    bad_key = GOOD_Q.model_copy(update={"answer_index": 9})
    dup = GOOD_Q.model_copy(update={"choices": ["A", "A", "B", "C"]})
    use_model(FakeChat(quiz=[bad_key, dup, GOOD_Q], solver=passage_solver))
    qs = client.post(f"/documents/{doc_id}/quiz", json={"num_questions": 3}).json()["questions"]
    assert len(qs) == 1


def test_quiz_fails_cleanly_when_nothing_usable(client, doc_id, use_model):
    use_model(FakeChat(quiz=[GOOD_Q.model_copy(update={"answer_index": 9})], solver=passage_solver))
    r = client.post(f"/documents/{doc_id}/quiz")
    assert r.status_code == 502


def test_question_count_is_validated(client, doc_id):
    assert client.post(f"/documents/{doc_id}/quiz", json={"num_questions": 0}).status_code == 422
    assert client.post(f"/documents/{doc_id}/quiz", json={"num_questions": 99}).status_code == 422


def test_quiz_questions_cover_the_whole_document():
    text = "\n\n".join(f"Section {i}. " + "Fact. " * 100 for i in range(40))
    plan = llm._pick_chunks(text, 5)
    assert sum(n for _, n in plan) == 5
    assert "Section 0." in plan[0][0] and "Section 3" in plan[-1][0]  # starts at the top, reaches the end


# --- Ollama problems ------------------------------------------------------------ #


class Broken:
    def __init__(self, exc):
        self.exc = exc

    def with_structured_output(self, schema):
        def run(_):
            raise self.exc

        return RunnableLambda(run)


def test_ollama_not_running_gives_503(client, doc_id, use_model):
    use_model(Broken(ConnectionError("Failed to connect to Ollama")))
    r = client.post(f"/documents/{doc_id}/summary")
    assert r.status_code == 503 and "ollama.com" in r.json()["detail"]
    use_model(Broken(httpx.ConnectError("refused")))
    assert client.post(f"/documents/{doc_id}/quiz").status_code == 503


def test_missing_model_gives_pull_instructions(client, doc_id, use_model):
    use_model(Broken(ollama.ResponseError("model not found", 404)))
    r = client.post(f"/documents/{doc_id}/summary")
    assert r.status_code == 503 and "ollama pull llama3.2" in r.json()["detail"]


def test_status_endpoint_when_ollama_is_down(client, monkeypatch):
    def boom(*a, **k):
        raise ConnectionError("down")

    monkeypatch.setattr(ollama.Client, "list", boom)
    body = client.get("/llm/status").json()
    assert body["reachable"] is False and "ollama.com" in body["hint"]
