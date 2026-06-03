from __future__ import annotations

from abc import ABC, abstractmethod

import httpx

from .config import settings


class EmbeddingProvider(ABC):
    @abstractmethod
    def embed(self, text: str) -> list[float]:
        raise NotImplementedError


class OllamaEmbeddingProvider(EmbeddingProvider):
    def __init__(self, base_url: str | None = None, model: str | None = None) -> None:
        self.base_url = (base_url or settings.ollama_url).rstrip("/")
        self.model = model or settings.embedding_model

    def embed(self, text: str) -> list[float]:
        response = httpx.post(
            f"{self.base_url}/api/embed",
            json={"model": self.model, "input": text},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        if "embeddings" in payload:
            return payload["embeddings"][0]
        if "embedding" in payload:
            return payload["embedding"]
        raise ValueError("Unexpected Ollama embedding response")


class OpenAIEmbeddingProvider(EmbeddingProvider):
    def __init__(self) -> None:
        if not settings.openai_api_key:
            raise ValueError(
                "UAM_OPENAI_API_KEY is required when embedding_provider='openai'"
            )
        self.api_key = settings.openai_api_key
        self.model = settings.openai_embedding_model
        self.base_url = settings.openai_base_url.rstrip("/")

    def embed(self, text: str) -> list[float]:
        response = httpx.post(
            f"{self.base_url}/embeddings",
            json={"model": self.model, "input": text, "dimensions": 768},
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()["data"][0]["embedding"]


def get_embedding_provider() -> EmbeddingProvider:
    if settings.embedding_provider == "openai":
        return OpenAIEmbeddingProvider()
    return OllamaEmbeddingProvider()
