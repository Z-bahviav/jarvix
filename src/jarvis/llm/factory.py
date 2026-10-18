from __future__ import annotations

from jarvis.config import LLMSettings, Settings
from jarvis.llm.base import LLMProvider
from jarvis.llm.gemini import GeminiProvider


class LLMConfigurationError(RuntimeError):
    pass


def build_llm_provider(settings: Settings, llm: LLMSettings) -> LLMProvider:
    provider = llm.provider.lower()
    if provider == "gemini":
        key = Settings.gemini_api_key()
        if not key:
            raise LLMConfigurationError(
                "Set JARVIS_GEMINI_API_KEY or GEMINI_API_KEY in the environment."
            )
        return GeminiProvider(llm, key)
    raise LLMConfigurationError(f"Unsupported LLM provider: {llm.provider}")
