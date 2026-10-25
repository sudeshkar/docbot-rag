from collections.abc import Iterator

from app.domain.types import RetrievedChunk
from app.rag.generation.citations import extract_citations
from app.rag.generation.llm import LLM, LLMResult
from app.rag.generation.prompt import PromptBuilder

REFUSAL_MESSAGE = "Sorry, I can't help with that request."

# Some open models cite as 【1】; map to [1] so citation parsing and the UI's hover cards work.
# Per-character, so it's safe even when a bracket arrives in its own stream delta.
CITATION_BRACKETS = str.maketrans({"【": "[", "】": "]"})


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
        for delta in self.llm.stream(system, messages, result):
            yield delta.translate(CITATION_BRACKETS)
        result.text = result.text.translate(CITATION_BRACKETS)
        if result.stop_reason == "refusal":
            result.text += REFUSAL_MESSAGE
            yield REFUSAL_MESSAGE
            result.cited_indices = []
            return
        result.cited_indices = extract_citations(result.text, len(chunks))
