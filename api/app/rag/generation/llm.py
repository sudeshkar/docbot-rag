import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Protocol

import anthropic
import httpx

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


class LLMError(Exception):
    """Provider-neutral failure (network, auth, rate limit) so callers needn't know which SDK is behind the port."""


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
        try:
            with self.client.beta.messages.stream(**self.request_params(system, messages)) as stream:
                for delta in stream.text_stream:
                    result.text += delta
                    yield delta
                final = stream.get_final_message()
        except anthropic.APIError as e:
            raise LLMError(str(e)) from e
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


class GroqLLM:
    """Adapter over Groq's OpenAI-compatible streaming Chat Completions API (SSE)."""

    def __init__(
        self,
        api_key: str,
        model: str,
        max_tokens: int = 4096,
        timeout: float = 60.0,
        transport: httpx.BaseTransport | None = None,
    ):
        if not api_key:
            raise ValueError("Groq LLM needs GROQ_API_KEY")
        self.model = model
        self.max_tokens = max_tokens
        # One pooled client for connection reuse (keep-alive) across calls.
        self._client = httpx.Client(
            timeout=timeout,
            transport=transport,
            headers={"Authorization": f"Bearer {api_key}"},
        )

    def request_body(self, system: str, messages: list[dict]) -> dict:
        return {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "system", "content": system}, *messages],
            "stream": True,
            "stream_options": {"include_usage": True},
        }

    def stream(self, system: str, messages: list[dict], result: LLMResult) -> Iterator[str]:
        try:
            yield from self._stream(system, messages, result)
        except httpx.HTTPStatusError as e:
            raise LLMError(f"Groq returned HTTP {e.response.status_code}: {e.response.text[:200]}") from e
        except httpx.HTTPError as e:
            raise LLMError(f"Groq request failed: {e}") from e

    def _stream(self, system: str, messages: list[dict], result: LLMResult) -> Iterator[str]:
        with self._client.stream("POST", GROQ_URL, json=self.request_body(system, messages)) as resp:
            if resp.is_error:
                resp.read()
                resp.raise_for_status()
            for line in resp.iter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                event = json.loads(data)
                # Usage arrives on the final chunk: top-level (OpenAI style) or under x_groq.
                usage = event.get("usage") or (event.get("x_groq") or {}).get("usage")
                if usage:
                    result.input_tokens = usage.get("prompt_tokens", 0)
                    result.output_tokens = usage.get("completion_tokens", 0)
                for choice in event.get("choices") or []:
                    if delta := (choice.get("delta") or {}).get("content"):
                        result.text += delta
                        yield delta
                    if reason := choice.get("finish_reason"):
                        result.stop_reason = reason
