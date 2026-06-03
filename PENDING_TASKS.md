# Pending Tasks for unified-agentic-memory

---

## Goal 2: Remote Model Support

- [x] **G2-1** — Extend `Settings` in `config.py` with `embedding_provider`, `llm_provider`, OpenAI fields (`openai_api_key`, `openai_embedding_model`, `openai_llm_model`, `openai_base_url`), and OpenRouter fields (`openrouter_api_key`, `openrouter_base_url`, `openrouter_llm_model`). Update `.env.example` with the new vars.
- [x] **G2-2** — Add `OpenAIEmbeddingProvider` to `embeddings.py` and a `get_embedding_provider()` factory function.
- [x] **G2-3** — Add `OpenAILLMProvider` and `OpenRouterLLMProvider` to `llm.py` and a `get_llm_provider()` factory function.
- [x] **G2-4** — Wire factory functions into all call sites: replace direct `OllamaEmbeddingProvider()` / `OllamaLLMProvider()` instantiation in `events.py`, `vectors.py`, and `dream.py`.
- [x] **G2-5** — Add `check-providers` CLI command that instantiates the configured providers and tests embed/generate; exits 0 on success, 1 on any failure.
- [x] **G2-6** — Add `tests/test_providers.py` covering both providers with mocked httpx responses and the factory functions.

---

## Deferred by design (v1 scope)

- **pg_cron scheduling policy** — `pg_cron` is installed and smoke-tested. Specific schedule cadence for the dream phase is intentionally deferred until real usage data is available.
- **Security hardening** — API has no authentication. Local single-user assumptions hold for v1. Add hardening before any remote or multi-user deployment.
- **Warp MCP integration** — Warp v1 uses skill + CLI only. MCP integration deferred.
- **Search/index tuning** — Cache TTL and RRF weights use default values. Tuning deferred until real data volume exists.
