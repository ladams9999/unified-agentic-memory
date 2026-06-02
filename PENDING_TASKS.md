# Pending Tasks for unified-agentic-memory

The items below are still open because they need live Docker/Ollama-backed verification, deeper integration coverage, or follow-up cleanup beyond the verified implementation pass.

---

## Runtime validation blocked by unavailable local services

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
