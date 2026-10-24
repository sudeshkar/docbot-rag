from collections.abc import Iterator

from app.domain.types import RetrievedChunk
from app.rag.generation.citations import extract_citations
from app.rag.generation.llm import LLM, LLMResult
from app.rag.generation.prompt import PromptBuilder

REFUSAL_MESSAGE = "Sorry, I can't help with that request."


class AnswerGenerator:
    def __init__(self, llm: LLM, prompts: PromptBuilder):
        self.llm = llm
        self.prompts = prompts

    def stream(
        self,
        question: str,
        chunks: list[RetrievedChunk],
        history: list[dict],
        instructions: str,
        result: LLMResult,
    ) -> Iterator[str]:
        system, messages = self.prompts.build(question, chunks, history, instructions)
        yield from self.llm.stream(system, messages, result)
        if result.stop_reason == "refusal":
            result.text += REFUSAL_MESSAGE
            yield REFUSAL_MESSAGE
            result.cited_indices = []
            return
        result.cited_indices = extract_citations(result.text, len(chunks))
