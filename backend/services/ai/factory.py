"""Factory for provider-agnostic AI clients."""

from __future__ import annotations

from backend.config import Settings
from backend.services.ai.base import AIProviderClient
from backend.services.ai.providers import AnthropicAIProvider, OpenAICompatibleAIProvider


DEFAULT_MODELS: dict[str, str] = {
    "anthropic": "claude-sonnet-4-20250514",
    "openai": "gpt-4.1-mini",
    "groq": "llama-3.3-70b-versatile",
    "ollama": "llama3.1",
}

OLLAMA_BASE_URL = "http://localhost:11434/v1"
OLLAMA_API_KEY = "ollama"
GROQ_BASE_URL = "https://api.groq.com/openai/v1"


def build_ai_provider_client(settings: Settings) -> AIProviderClient:
    """Build the configured AI provider client."""

    provider = settings.AI_PROVIDER.lower()
    model = settings.AI_MODEL or DEFAULT_MODELS[provider]

    if provider == "anthropic":
        return AnthropicAIProvider(api_key=_require_api_key(settings), model=model)
    if provider == "openai":
        return OpenAICompatibleAIProvider(api_key=_require_api_key(settings), model=model)
    if provider == "groq":
        return OpenAICompatibleAIProvider(
            api_key=_require_api_key(settings),
            model=model,
            base_url=GROQ_BASE_URL,
        )
    if provider == "ollama":
        return OpenAICompatibleAIProvider(
            api_key=OLLAMA_API_KEY,
            model=model,
            base_url=OLLAMA_BASE_URL,
        )

    raise ValueError(f"Unsupported AI provider: {settings.AI_PROVIDER}")


def _require_api_key(settings: Settings) -> str:
    api_key = settings.AI_PROVIDER_API_KEY
    if not api_key:
        raise RuntimeError("AI_PROVIDER_API_KEY is required for the configured AI provider.")
    return api_key
