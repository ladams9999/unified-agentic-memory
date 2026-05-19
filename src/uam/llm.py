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
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        return payload["response"].strip()
