"""One chat turn (retrieve -> generate -> persist), shared by the playground and the public widget.
Emits Server-Sent Events so the UI can render tokens as they arrive."""

import json
import logging
import time
from collections.abc import Iterator
from typing import Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import Bot, QueryLog
from app.domain.types import RetrievalResult
from app.rag.generation.answer import AnswerGenerator
from app.rag.generation.llm import LLMError, LLMResult
from app.repositories.bots import month_start
from app.repositories.conversations import ConversationRepository
from app.repositories.query_logs import QueryLogRepository

log = logging.getLogger(__name__)

SNIPPET_CHARS = 400


class Retrieval(Protocol):
    def retrieve(self, bot_id: UUID, query: str, top_n: int) -> RetrievalResult: ...


def sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


class ChatService:
    def __init__(
        self,
        db: Session,
        retrieval: Retrieval,
        generator: AnswerGenerator,
        context_k: int = 6,
        history_messages: int = 6,
        low_confidence_score: float = 0.35,
    ):
        self.db = db
        self.retrieval = retrieval
        self.generator = generator
        self.context_k = context_k
        self.history_messages = history_messages
        self.low_confidence_score = low_confidence_score
        self.conversations = ConversationRepository(db)
        self.logs = QueryLogRepository(db)

    def chat_turn(self, bot: Bot, question: str, conversation_id: UUID | None, channel: str) -> Iterator[str]:
        started = time.perf_counter()
        if self.logs.count_since(bot.id, month_start()) >= bot.monthly_quota:
            yield sse("error", {"message": "This assistant has reached its monthly message limit."})
            return

        conv = self.conversations.get_or_create(bot.id, conversation_id, channel)
        history = self.conversations.recent_messages(conv.id, self.history_messages)
        self.db.commit()  # persist the conversation before the slow LLM call
        yield sse("meta", {"conversation_id": str(conv.id)})

        result = self.retrieval.retrieve(bot.id, question, self.context_k)
        sources = [
            {
                "index": i,
                "document_id": c.document_id,
                "title": c.document_title,
                "heading": c.heading,
                "url": c.source_url,
                "page": c.meta.get("page"),
                "snippet": c.content[:SNIPPET_CHARS],
            }
            for i, c in enumerate(result.chunks, start=1)
        ]

        llm = LLMResult()
        try:
            for delta in self.generator.stream(question, result.chunks, history, bot.instructions, llm):
                yield sse("token", delta)
        except LLMError as e:
            log.warning("LLM call failed: %s", e)
            yield sse("error", {"message": "The assistant is temporarily unavailable. Please try again."})
            return

        cited = [sources[i - 1] for i in llm.cited_indices]
        answered = bool(cited)
        yield sse("sources", cited)

        message = self.conversations.add_turn(conv.id, question, llm.text, cited)
        self.logs.add(
            QueryLog(
                bot_id=bot.id,
                conversation_id=conv.id,
                channel=channel,
                question=question,
                top_score=result.top_vector_score,
                answered=answered,
                cited_document_ids=sorted({s["document_id"] for s in cited}),
                latency_ms=int((time.perf_counter() - started) * 1000),
                input_tokens=llm.input_tokens,
                output_tokens=llm.output_tokens,
            )
        )
        self.db.commit()
        yield sse(
            "done",
            {
                "message_id": str(message.id),
                "answered": answered,
                "low_confidence": result.top_vector_score < self.low_confidence_score,
            },
        )
