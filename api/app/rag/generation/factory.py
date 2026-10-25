from app.rag.generation.llm import LLM, ClaudeLLM, GroqLLM


def create_llm(
    provider: str,
    anthropic_api_key: str | None = None,
    llm_model: str = "claude-opus-5-5",
    llm_effort: str = "low",
    llm_fallbacks: bool = True,
    groq_api_key: str | None = None,
    groq_model: str = "openai/gpt-oss-120b",
) -> LLM:
    if provider == "anthropic":
        return ClaudeLLM(anthropic_api_key, llm_model, llm_effort, llm_fallbacks)
    if provider == "groq":
        return GroqLLM(api_key=groq_api_key or "", model=groq_model)
    raise ValueError(f"Unknown LLM provider '{provider}'. Options: anthropic, groq")
