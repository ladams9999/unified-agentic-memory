from __future__ import annotations

from abc import ABC, abstractmethod

import httpx

from .config import settings


class LLMProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str, system: str) -> str:
        raise NotImplementedError


class OllamaLLMProvider(LLMProvider):
    def __init__(self, base_url: str | None = None, model: str | None = None) -> None:
        self.base_url = (base_url or settings.ollama_url).rstrip("/")
        self.model = model or settings.llm_model

    def generate(self, prompt: str, system: str) -> str:
        response = httpx.post(
            f"{self.base_url}/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "system": system,
                "stream": False,
            },
            timeout=settings.llm_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        return payload["response"].strip()


class OpenAILLMProvider(LLMProvider):
    def __init__(self) -> None:
        if not settings.openai_api_key:
            raise ValueError(
                "UAM_OPENAI_API_KEY is required when llm_provider='openai'"
            )
        self.api_key = settings.openai_api_key
        self.model = settings.openai_llm_model
        self.base_url = settings.openai_base_url.rstrip("/")

    def generate(self, prompt: str, system: str) -> str:
        response = httpx.post(
            f"{self.base_url}/chat/completions",
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            },
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=settings.llm_timeout_seconds,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()


class OpenRouterLLMProvider(LLMProvider):
    def __init__(self) -> None:
        if not settings.openrouter_api_key:
            raise ValueError(
                "UAM_OPENROUTER_API_KEY is required when llm_provider='openrouter'"
            )
        self.api_key = settings.openrouter_api_key
        self.model = settings.openrouter_llm_model
        self.base_url = settings.openrouter_base_url.rstrip("/")

    def generate(self, prompt: str, system: str) -> str:
        response = httpx.post(
            f"{self.base_url}/chat/completions",
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            },
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "HTTP-Referer": "https://github.com/unified-agentic-memory",
            },
            timeout=settings.llm_timeout_seconds,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()


def get_llm_provider() -> LLMProvider:
    if settings.llm_provider == "ollama":
        return OllamaLLMProvider()
    if settings.llm_provider == "openai":
        return OpenAILLMProvider()
    if settings.llm_provider == "openrouter":
        return OpenRouterLLMProvider()
    raise ValueError(
        f"Unknown LLM provider {settings.llm_provider!r}. "
        "Set UAM_LLM_PROVIDER to 'ollama', 'openai', or 'openrouter'."
    )
