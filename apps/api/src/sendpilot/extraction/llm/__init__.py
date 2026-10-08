"""LLM client selection: real Anthropic when a key is set, fake otherwise."""

from __future__ import annotations

from ...config import settings
from .client import LLMClient
from .fake_client import FakeLLMClient


def get_llm_client() -> LLMClient:
    if settings.anthropic_api_key:
        from .anthropic_client import AnthropicLLMClient

        return AnthropicLLMClient()
    return FakeLLMClient()


__all__ = ["LLMClient", "get_llm_client"]
