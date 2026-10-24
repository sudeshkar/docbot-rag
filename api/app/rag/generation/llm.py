from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Protocol

import anthropic


@dataclass
class LLMResult:
    """Filled in by the LLM as it streams; read after the stream is exhausted."""

    text: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    stop_reason: str | None = None
    cited_indices: list[int] = field(default_factory=list)


class LLM(Protocol):
    def stream(self, system: str, messages: list[dict], result: LLMResult) -> Iterator[str]: ...


class ClaudeLLM:
    """Adapter over the Anthropic SDK's streaming Messages API."""

    FALLBACK_BETA = "server-side-fallback-2026-07-01"

    def __init__(self, api_key: str | None, model: str, effort: str = "low",
                 fallbacks: bool = True, max_tokens: int = 4096):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.effort = effort
        self.fallbacks = fallbacks
        self.max_tokens = max_tokens

    def request_params(self, system: str, messages: list[dict]) -> dict:
        params: dict = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": system,
            "messages": messages,
            "output_config": {"effort": self.effort},
        }
        if self.fallbacks:
            # If a safety classifier declines, the API re-runs the request on a fallback model in-call.
            params["betas"] = [self.FALLBACK_BETA]
            params["fallbacks"] = "default"
        return params

    def stream(self, system: str, messages: list[dict], result: LLMResult) -> Iterator[str]:
        with self.client.beta.messages.stream(**self.request_params(system, messages)) as stream:
            for delta in stream.text_stream:
                result.text += delta
                yield delta
            final = stream.get_final_message()
        result.input_tokens = final.usage.input_tokens
        result.output_tokens = final.usage.output_tokens
        result.stop_reason = final.stop_reason

    def complete(self, prompt: str, max_tokens: int = 1024) -> str:
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
            output_config={"effort": "low"},
        )
        return "".join(b.text for b in resp.content if b.type == "text")
