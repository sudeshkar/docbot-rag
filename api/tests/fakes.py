"""Test doubles shared across service and API tests."""

from app.domain.types import RetrievalResult, RetrievedChunk
from app.rag.generation.llm import LLMError, LLMResult


class FakeLLM:
    def __init__(self, answer="Refunds take 5 days [1].", stop_reason="end_turn"):
        self.answer = answer
        self.stop_reason = stop_reason
        self.calls = []

    def stream(self, system, messages, result: LLMResult):
        self.calls.append((system, messages))
        for word in self.answer.split(" "):
            delta = word + " "
            result.text += delta
            yield delta
        result.input_tokens, result.output_tokens, result.stop_reason = 100, 20, self.stop_reason

    def complete(self, prompt, max_tokens=1024):
        return "5"


class FailingLLM:
    def stream(self, system, messages, result: LLMResult):
        raise LLMError("provider down")
        yield  # pragma: no cover - makes this a generator


class FakeRetrieval:
    def __init__(self, chunks=None, top_vector_score=0.8):
        self.chunks = chunks if chunks is not None else [
            RetrievedChunk("c1", "d1", "Help Center", None, "Billing > Refunds",
                           "Refunds take 5 business days.", {}, 0.03, {"vector": 0.8}),
        ]
        self.top_vector_score = top_vector_score
        self.calls = []

    def retrieve(self, bot_id, query, top_n):
        self.calls.append((bot_id, query, top_n))
        return RetrievalResult(chunks=self.chunks, top_vector_score=self.top_vector_score)


class FakeEmbedder:
    def embed_documents(self, texts):
        return [[1.0, 0.0] for _ in texts]

    def embed_query(self, text):
        return [1.0, 0.0]


class FakeStore:
    def __init__(self):
        self.upserts, self.deleted, self.dropped = [], [], []

    def upsert(self, namespace, ids, embeddings, documents, metadatas):
        self.upserts.append((namespace, ids))

    def query(self, namespace, embedding, k):
        return []

    def delete_document(self, namespace, document_id):
        self.deleted.append((namespace, document_id))

    def drop_namespace(self, namespace):
        self.dropped.append(namespace)

    def ping(self):
        return True


def parse_sse(body: str) -> list[tuple[str, object]]:
    import json

    events = []
    for block in body.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line)
        events.append((lines["event"], json.loads(lines["data"])))
    return events
