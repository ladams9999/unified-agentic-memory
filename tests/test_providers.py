"""Tests for OpenAI and OpenRouter provider implementations and factories."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

import pytest

from uam import embeddings as emb_module
from uam import llm as llm_module
from uam.embeddings import (
    OllamaEmbeddingProvider,
    OpenAIEmbeddingProvider,
    get_embedding_provider,
)
from uam.llm import (
    OllamaLLMProvider,
    OpenAILLMProvider,
    OpenRouterLLMProvider,
    get_llm_provider,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_response(json_data: dict) -> MagicMock:
    """Return a mock httpx.Response that yields json_data from .json()."""
    resp = MagicMock()
    resp.json.return_value = json_data
    resp.raise_for_status.return_value = None
    return resp


EMBEDDING_RESPONSE = {"data": [{"embedding": [0.1] * 768}]}
LLM_RESPONSE = {"choices": [{"message": {"content": "hello"}}]}


# ---------------------------------------------------------------------------
# OpenAIEmbeddingProvider
# ---------------------------------------------------------------------------


def test_openai_embedding_provider_raises_without_key():
    with patch.object(emb_module.settings, "openai_api_key", ""):
        with pytest.raises(ValueError, match="UAM_OPENAI_API_KEY"):
            OpenAIEmbeddingProvider()


def test_openai_embedding_provider_embed():
    with (
        patch.object(emb_module.settings, "openai_api_key", "sk-test"),
        patch("uam.embeddings.httpx.post", return_value=_fake_response(EMBEDDING_RESPONSE)) as mock_post,
    ):
        provider = OpenAIEmbeddingProvider()
        result = provider.embed("hello world")

    assert isinstance(result, list)
    assert len(result) == 768
    assert all(v == 0.1 for v in result)

    call_kwargs = mock_post.call_args
    assert "dimensions" in call_kwargs.kwargs.get("json", call_kwargs[1].get("json", {})) or \
           "dimensions" in (call_kwargs[0][1] if len(call_kwargs[0]) > 1 else {})


def test_openai_embedding_provider_sends_dimensions():
    with (
        patch.object(emb_module.settings, "openai_api_key", "sk-test"),
        patch("uam.embeddings.httpx.post", return_value=_fake_response(EMBEDDING_RESPONSE)) as mock_post,
    ):
        OpenAIEmbeddingProvider().embed("test")

    posted_json = mock_post.call_args[1]["json"]
    assert posted_json["dimensions"] == 768


# ---------------------------------------------------------------------------
# OpenAILLMProvider
# ---------------------------------------------------------------------------


def test_openai_llm_provider_raises_without_key():
    with patch.object(llm_module.settings, "openai_api_key", ""):
        with pytest.raises(ValueError, match="UAM_OPENAI_API_KEY"):
            OpenAILLMProvider()


def test_openai_llm_provider_generate():
    with (
        patch.object(llm_module.settings, "openai_api_key", "sk-test"),
        patch("uam.llm.httpx.post", return_value=_fake_response(LLM_RESPONSE)),
    ):
        provider = OpenAILLMProvider()
        result = provider.generate("Say hello.", "You are a test.")

    assert result == "hello"


def test_openai_llm_provider_sends_messages():
    with (
        patch.object(llm_module.settings, "openai_api_key", "sk-test"),
        patch("uam.llm.httpx.post", return_value=_fake_response(LLM_RESPONSE)) as mock_post,
    ):
        OpenAILLMProvider().generate("Say hello.", "system prompt")

    posted_json = mock_post.call_args[1]["json"]
    messages = posted_json["messages"]
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == "system prompt"
    assert messages[1]["role"] == "user"
    assert messages[1]["content"] == "Say hello."


# ---------------------------------------------------------------------------
# OpenRouterLLMProvider
# ---------------------------------------------------------------------------


def test_openrouter_llm_provider_raises_without_key():
    with patch.object(llm_module.settings, "openrouter_api_key", ""):
        with pytest.raises(ValueError, match="UAM_OPENROUTER_API_KEY"):
            OpenRouterLLMProvider()


def test_openrouter_llm_provider_generate():
    with (
        patch.object(llm_module.settings, "openrouter_api_key", "or-test"),
        patch("uam.llm.httpx.post", return_value=_fake_response(LLM_RESPONSE)),
    ):
        provider = OpenRouterLLMProvider()
        result = provider.generate("Say hello.", "You are a test.")

    assert result == "hello"


def test_openrouter_llm_provider_sends_referer_header():
    with (
        patch.object(llm_module.settings, "openrouter_api_key", "or-test"),
        patch("uam.llm.httpx.post", return_value=_fake_response(LLM_RESPONSE)) as mock_post,
    ):
        OpenRouterLLMProvider().generate("Say hello.", "system")

    headers = mock_post.call_args[1]["headers"]
    assert "HTTP-Referer" in headers
    assert "unified-agentic-memory" in headers["HTTP-Referer"]


# ---------------------------------------------------------------------------
# Factory: get_embedding_provider
# ---------------------------------------------------------------------------


def test_get_embedding_provider_returns_ollama_by_default():
    with patch.object(emb_module.settings, "embedding_provider", "ollama"):
        provider = get_embedding_provider()
    assert isinstance(provider, OllamaEmbeddingProvider)


def test_get_embedding_provider_returns_openai():
    with (
        patch.object(emb_module.settings, "embedding_provider", "openai"),
        patch.object(emb_module.settings, "openai_api_key", "sk-test"),
    ):
        provider = get_embedding_provider()
    assert isinstance(provider, OpenAIEmbeddingProvider)


# ---------------------------------------------------------------------------
# Factory: get_llm_provider
# ---------------------------------------------------------------------------


def test_get_llm_provider_returns_ollama_by_default():
    with patch.object(llm_module.settings, "llm_provider", "ollama"):
        provider = get_llm_provider()
    assert isinstance(provider, OllamaLLMProvider)


def test_get_llm_provider_returns_openai():
    with (
        patch.object(llm_module.settings, "llm_provider", "openai"),
        patch.object(llm_module.settings, "openai_api_key", "sk-test"),
    ):
        provider = get_llm_provider()
    assert isinstance(provider, OpenAILLMProvider)


def test_get_llm_provider_returns_openrouter():
    with (
        patch.object(llm_module.settings, "llm_provider", "openrouter"),
        patch.object(llm_module.settings, "openrouter_api_key", "or-test"),
    ):
        provider = get_llm_provider()
    assert isinstance(provider, OpenRouterLLMProvider)


def test_get_embedding_provider_raises_on_unknown():
    with patch.object(emb_module.settings, "embedding_provider", "openAi"):
        with pytest.raises(ValueError, match="Unknown embedding provider"):
            get_embedding_provider()


def test_get_llm_provider_raises_on_unknown():
    with patch.object(llm_module.settings, "llm_provider", "grok"):
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            get_llm_provider()
