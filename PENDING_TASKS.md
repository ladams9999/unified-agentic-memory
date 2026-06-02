# Pending Tasks for unified-agentic-memory

The items below are still open because they need live Docker/Ollama-backed verification, deeper integration coverage, or follow-up cleanup beyond the verified implementation pass.

---

## Goal 1: Documentation Alignment

- [ ] **G1-1** Rewrite `AGENTS.md` with substantive project summary: what UAM is, architecture overview, key files, and how to run the stack — useful for a coding agent starting cold.
- [ ] **G1-2** Audit `README.md` against current hook formats (Claude Code nested-hooks format, Copilot CLI `cwd`-based format, Windows path quoting) and update any stale instructions.
- [ ] **G1-3** Delete the stale `copilot-session-*.md` artifact from the repo root.

---

## Runtime validation blocked by unavailable local services

- [ ] **P0-3** Validate pg_cron extension creation inside the `postgres` database after container startup.
- [ ] **P0-8** Apply the migration runner end to end against a fresh Postgres instance and verify idempotent re-runs.
- [ ] **P1a-1** Verify the AGE graph `uam` exists after fresh DB initialization.
- [ ] **P1a-1b** Verify the append-only `uam.events` relational table in a live database.
- [ ] **P1a-2** Verify the `uam.memories` table in a live database.
- [ ] **P1a-3** Verify the `uam.embeddings` table and HNSW indexes in a live database.
- [ ] **P1a-4** Verify the `uam.dream_runs` table in a live database.
- [ ] **P1a-5** Verify the `uam.search_cache` table in a live database.
- [ ] **P1a-6** Verify the GIN full-text indexes in a live database.
- [ ] **P1a-7** Verify docker-compose init creates schema and graph on a fresh container.
- [ ] **P1a-8** Verify operational event indexes in a live database.
- [ ] **P1b-3** Validate psycopg pool connectivity plus `ensure_age()` against a running database.
- [ ] **P1b-5** Validate live Ollama embeddings return 768 dimensions.
- [ ] **P1b-6** Validate vector storage and similarity search against pgvector.
- [ ] **P1b-8** Validate end-to-end event logging into relational, graph, and vector stores.
- [ ] **P1b-11** Validate projection replay against a live AGE graph.
- [ ] **P2-2** Validate injector search/profile responses against seeded memories.
- [ ] **P3-1** Validate live Ollama prose generation through `OllamaLLMProvider`.
- [ ] **P3-4** Validate `uv run python -m uam.cli dream` end to end with Docker and Ollama available.
- [ ] **P3-6** Run the pg_cron smoke test against live pg_cron metadata tables.
- [ ] **P4-4** Validate the `search` CLI command against a seeded live database.
- [ ] **P5-1** Validate MCP handshake with a real MCP client.
- [ ] **P5-2** Validate MCP tool calls against a running backend.
- [ ] **P6-1** Validate `GET /stats` returns JSON from a running FastAPI app with a live database.
- [ ] **P6-3** Validate the search UI against the API.
- [ ] **P6-4** Validate the memory browser UI against the API.
- [ ] **P6-5** Validate the session browser UI against the API.
- [ ] **P6-6** Validate the stats dashboard UI against the API.
- [ ] **P7-9** Run the full documented local smoke sequence on a clean machine.
