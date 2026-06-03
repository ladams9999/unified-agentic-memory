# Completed Tasks for unified-agentic-memory

The items below were completed and verified in this implementation pass.

---

## Phase 0: Fixes & Project Init

- [x] **P0-1** Remove `timescaledb` from `shared_preload_libraries` in `db_stack/Dockerfile_pguam18.4`; keep only `pg_cron`.
- [x] **P0-2** Pin Apache AGE clone to `PG18/v1.7.0-rc0` tag with `--depth 1` in `db_stack/Dockerfile_pguam18.4`.
- [x] **P0-2b** Pin pgvector clone to `v0.8.2` with `--depth 1` in `db_stack/Dockerfile_pguam18.4`.
- [x] **P0-4** Update `db_stack/docker-compose.yml` to bind-mount `./db_data/` for Postgres data instead of a named volume.
- [x] **P0-5** Copy `db_stack/.env` to `db_stack/.env.example`, ignore `db_stack/.env`, and prepare it for removal from git tracking.
- [x] **P0-6** Create the project `.gitignore` with local environment, Python, Node, and Postgres bind-mount exclusions.
- [x] **P0-7** Initialize the `uv` project, pin Python 3.13, add `uuid6`, and verify UUID7 generation.

## Phase 1b: Core Python Library

- [x] **P1b-0** Create importable `uam` and `uam.hooks` packages.
- [x] **P1b-4** Create `uam/graph.py` with session, event, link, and ordered retrieval helpers plus unit coverage.
- [x] **P1b-7** Create `uam/memories.py` with CRUD operations and embedding refresh-on-change behavior plus unit coverage.
- [x] **P1b-9** Create `uam/cli.py` with the requested command surface (`search`, `store`, `get`, `delete`, `list`, `sessions`, `dream`, `migrate`).

## Phase 2: Hook System

- [x] **P2-0** Define and document the hook stdout injection contract in `uam/hooks/injector.py`.
- [x] **P2-1** Create `uam/hooks/handler.py` with client normalization, structured logging, non-blocking failure behavior, and generated session IDs when absent.
- [x] **P2-3** Create Claude Code hook config template at `hooks/claude-code/settings.json`.
- [x] **P2-4** Create Codex hook config template at `hooks/codex/hooks.json`.
- [x] **P2-5** Create GitHub Copilot hook config template at `hooks/copilot/hooks.json`.
- [x] **P2-6** Create Warp skill at `hooks/warp/uam-memory/SKILL.md`.
- [x] **P2-7** Add hook latency/error metrics with rolling summary output in local logs.

## Phase 3: Dream Phase

- [x] **P3-0** Define the dream output format in `uam/dream.py`.
- [x] **P3-2** Create `uam/dream.py` with prompt building, parsing, watermarking, and memory upserts.
- [x] **P3-3** Create the dream prompt template with merge/overwrite behavior.
- [x] **P3-5** Invalidate search cache after dream completion.
- [x] **P3-7** Document dream scheduling as deferred in v1.

## Phase 4: Search

- [x] **P4-1** Create `uam/search.py` with hybrid search.
- [x] **P4-2** Implement Reciprocal Rank Fusion reranking.
- [x] **P4-3** Implement TTL-based search caching with lazy pruning.

## Phase 6: API & Web Interface

- [x] **P6-2** Initialize the React frontend with Vite in `frontend/`.

## Element 2: Memory types — fact / learning / idea + idea promotion

- [x] **T1** — Added `db_stack/migrations/0002_memory_type.sql`: `memory_type TEXT NOT NULL DEFAULT 'learning' CHECK (memory_type IN ('fact', 'learning', 'idea'))`.
- [x] **T2** — Added `MemoryType` enum (`fact`, `learning`, `idea`) to `src/uam/models.py`; added `memory_type: MemoryType = MemoryType.learning` to `Memory`.
- [x] **T3** — Updated all SQL in `src/uam/memories.py` to include `memory_type`; `_memory_from_row()` reads column index 4 for type, shifting embedding/timestamps; `upsert_memory()` accepts `memory_type` param.
- [x] **T4** — `upsert_memory()` raises `ValueError` if existing record has `memory_type='fact'`.
- [x] **T5** — Added `confirm_idea(path)` to `src/uam/memories.py`; raises if missing or not an idea, else sets `memory_type='learning'`.
- [x] **T6** — `src/uam/mcp_server.py`: added `uam_confirm_idea` tool; `uam_store` now accepts `memory_type` param (fact writes flow through upsert guard automatically).
- [x] **T7** — Updated `DREAM_OUTPUT_FORMAT` in `src/uam/dream.py` to require `type:` in frontmatter with definitions of each type. `parse_memory_blocks()` extracts and returns `MemoryType`; invalid values default to `learning`. Dream silently skips fact-overwrite errors.
- [x] **T8** — Added `confirm-idea <path>` subcommand to CLI; `store` accepts `--memory-type` option. `memory_type` appears in all `model_dump_json` outputs automatically.

## Element 1: Memory projection into graph (directory hierarchy)

- [x] **G1** — Added `ensure_path_nodes()`, `upsert_memory_node()`, and `delete_memory_node()` to `src/uam/graph.py`. Creates `:Directory` nodes per path segment with `:CHILD` edges; `:Memory` nodes store `{id, path}` only (reference, no content duplication). Orphaned directory nodes pruned on delete.
- [x] **G2** — Added `project_memory()`, `remove_memory_projection()`, and `replay_relational_memories()` to `src/uam/projection.py`.
- [x] **G3** — `upsert_memory()` calls `project_memory()` after upsert; `delete_memory()` calls `remove_memory_projection()` after delete (both use same connection; graph errors are non-fatal).
- [x] **G4** — `replay_relational_memories()` wired into `migrate` CLI command; output reports `memories_projected` count.
- [x] **G5** — Unit tests added to `tests/test_graph.py`: path hierarchy creation, memory node upsert with parent attachment, flat-path upsert (no parent), delete with orphan pruning, `project_memory` delegation, and `replay_relational_memories` bulk projection. All 15 tests pass.

## Goal 6: Full Smoke Sequence & Final Cleanup

- [x] **P7-9** Ran full README smoke sequence end-to-end: Docker build, migrate (idempotent), hook handler injection, search, dream dry-run — all pass cleanly.
- [x] Updated README smoke sequence: added prerequisites block (Ollama models), explicit `.env` setup step, copy-pasteable hook payload command.
- [x] Updated IMPLEMENTATION.md: added LLM model selection note documenting phi4-mini failure and mistral as working choice.
- [x] Pruned PENDING_TASKS.md: all validated tasks moved to COMPLETED_TASKS; remaining items documented as deferred with rationale.

## Goal 5: API, MCP, and Frontend Validation

- [x] **P6-1** Validated all 9 FastAPI endpoints return correct JSON against live DB.
- [x] **P5-1** Validated MCP handshake: `initialize` request returns valid `protocolVersion` and capabilities.
- [x] **P5-2** Validated `uam_search`, `uam_store`, and `uam_dream` MCP tool functions against live DB and Ollama.
- [x] **P6-3** Validated search UI: form renders, API wired correctly.
- [x] **P6-4** Validated memory browser: 5 paths listed, content preview works.
- [x] **P6-5** Validated session browser: 8 sessions listed, event timeline loads on click.
- [x] **P6-6** Validated stats dashboard: 14 events / 5 memories / 3 dream runs rendered correctly.
- [x] **fix** Added CORS middleware to `api.py` — frontend was blocked by missing `Access-Control-Allow-Origin`.
- [x] **fix** Excluded `embedding` field from memory API responses — was leaking full 768-dim vectors.

## Goal 4: Dream Phase & Search Validation

- [x] **P3-1** Validated live Ollama prose generation through `OllamaLLMProvider` using `mistral` model; phi4-mini discarded due to repetitive-token failure on structured-output prompts.
- [x] **P3-4** Validated `uv run uam dream` end-to-end: 13 events processed, 1 memory written, watermark set; incremental re-run processed only 1 new event.
- [x] **P3-6** Validated dream watermark: `uam.dream_runs` row present after run; second run processed only events after watermark.
- [x] **P4-4** Validated `uv run uam search` returns ranked hybrid results; cache populated on first hit, cleared to 0 rows after next dream run.
- [x] **fix** Updated default `llm_model` in `config.py` from `phi4-mini` to `mistral`.
- [x] **fix** Fixed `--dry-run` bug in `dream.py`: dry runs no longer write to `uam.dream_runs` or advance the watermark.

## Goal 3: End-to-End Event Ingest & Hook Validation

- [x] **P1b-8** Validated all 6 event types (SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, Stop, SessionEnd) through handler against live DB; rows confirmed in `uam.events`, `uam.embeddings`, and AGE graph.
- [x] **P1b-6** Validated vector similarity search returns ranked results from both event embeddings and memory embeddings.
- [x] **P1b-11** Validated projection replay: `replay_relational_events` processed all 11 events; `NEXT_EVENT` chain edges created in AGE graph.
- [x] **P2-2** Validated injection: `SessionStart` emits `{"system": "..."}` with profile memory content; `UserPromptSubmit` emits `{"userPrompt": "..."}` with hybrid search results.
- [x] **fix** Added `close_pool()` call to `handler.py` finally block — eliminates 5-second thread timeout on hook exit.

## Goal 2: Environment Bootstrap & Schema Validation

- [x] **P0-3** Validated pg_cron 1.6 installed in the `postgres` database.
- [x] **P0-8** Applied migration runner end-to-end; confirmed idempotent re-run returns `{"applied": []}` with no errors.
- [x] **P1a-1** Verified AGE graph `uam` exists after docker-compose init.
- [x] **P1a-1b** Verified append-only `uam.events` table with `raw_payload JSONB` and normalized columns.
- [x] **P1a-2** Verified `uam.memories` table with semantic path, frontmatter, content, embedding, and FTS columns.
- [x] **P1a-3** Verified `uam.embeddings` table; HNSW index `uam_embeddings_embedding_hnsw_idx` present.
- [x] **P1a-4** Verified `uam.dream_runs` table.
- [x] **P1a-5** Verified `uam.search_cache` table.
- [x] **P1a-6** Verified GIN FTS indexes on `uam.events` and `uam.memories`; FTS triggers confirmed.
- [x] **P1a-7** Verified docker-compose init scripts create schema, AGE graph, and all tables on fresh container.
- [x] **P1a-8** Verified operational event indexes (session_id, client, event_name, occurred_at).
- [x] **P1b-3** Validated psycopg pool connects to `uam_db` on PostgreSQL 18.4; `ensure_age()` sets `ag_catalog` in `search_path`.
- [x] **P1b-5** Validated `nomic-embed-text` via `OllamaEmbeddingProvider` returns 768-dimension vectors.

## Goal 2: Remote Model Support

- [x] **G2-1** — Extended `Settings` in `config.py` with `embedding_provider`, `llm_provider`, OpenAI fields, and OpenRouter fields. Created root `.env.example` documenting all UAM env vars including the new provider settings.
- [x] **G2-2** — Added `OpenAIEmbeddingProvider` to `embeddings.py` (POSTs to OpenAI `/embeddings` with `dimensions=768`); added `get_embedding_provider()` factory returning the right provider based on `settings.embedding_provider`.
- [x] **G2-3** — Added `OpenAILLMProvider` and `OpenRouterLLMProvider` to `llm.py`; both use OpenAI chat completions format; OpenRouter adds `HTTP-Referer` header. Added `get_llm_provider()` factory.

## Goal 1: Documentation Alignment

- [x] **G1-1** Rewrote `AGENTS.md` with substantive project summary: architecture, key files table, schema overview, run instructions, hook deployment, and testing notes.
- [x] **G1-2** Audited `README.md` against current hook formats — Claude Code nested format, Copilot CLI `cwd`-based format, Windows path quoting, and deployment architecture all confirmed accurate and up to date.
- [x] **G1-3** Deleted the stale `copilot-session-14523fc4-57e7-46ee-adb3-a46a84982d37.md` artifact from the repo root.

## Phase 7: Testing & Documentation

- [x] **P7-1** Set up `pytest` collection and a local fake-connection testing approach.
- [x] **P7-2** Write graph unit tests.
- [x] **P7-3** Write memory CRUD unit tests.
- [x] **P7-4** Write search unit tests.
- [x] **P7-5** Write hook handler unit tests.
- [x] **P7-6** Write dream phase unit tests.
- [x] **P7-7** Update `README.md` with setup, usage, hook installation, and dream phase sections.
- [x] **P7-8** Update `IMPLEMENTATION.md` with architecture, schema, and design details.
