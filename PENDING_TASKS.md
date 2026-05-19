# Pending Tasks for unified-agentic-memory

Tasks below break work into small, individually pickable work items. Paths are relative to this file unless noted.

---

## Phase 0: Fixes & Project Init

- [ ] **P0-1** Remove `timescaledb` from `shared_preload_libraries` in `db_stack/Dockerfile_pguam18.4`; keep only `pg_cron`.
  - Verify: Line reads `shared_preload_libraries = 'pg_cron'`.

- [ ] **P0-2** Pin Apache AGE clone to `PG18/v1.7.0-rc0` tag with `--depth 1` in `db_stack/Dockerfile_pguam18.4`.
  - Verify: `git clone --branch PG18/v1.7.0-rc0 --depth 1 https://github.com/apache/age.git`.

- [ ] **P0-2b** Pin pgvector clone to its latest stable release tag with `--depth 1` in `db_stack/Dockerfile_pguam18.4` (currently cloned from master with no pin).
  - Verify: `git clone --branch <tag> --depth 1 https://github.com/pgvector/pgvector.git` — look up latest stable tag before editing.

- [ ] **P0-3** Add pg_cron extension creation. Because pg_cron must be created in the `postgres` database, add a separate init script (e.g., `db_stack/create_pgcron.sh`) that runs `CREATE EXTENSION IF NOT EXISTS pg_cron;` against the `postgres` DB.
  - Verify: After container start, `\dx` in the `postgres` DB shows `pg_cron`.

- [ ] **P0-4** Update `db_stack/docker-compose.yml` to bind-mount `./db_data/` for Postgres data instead of the named `uam_data` volume.
  - Verify: `docker compose up` writes data to `./db_data/`.

- [ ] **P0-5** Copy `db_stack/.env` to `db_stack/.env.example`. Add `db_stack/.env` to `.gitignore`. Remove `db_stack/.env` from git tracking (`git rm --cached`).
  - Verify: `git status` shows `.env` untracked; `.env.example` is committed.

- [ ] **P0-6** Create `.gitignore` at project root with entries for `.env`, `db_data/`, `__pycache__/`, `.venv/`, `*.pyc`, `node_modules/`, `.uv/`. Note: `db_stack/uam_data/` is the markdown memory archive directory and is NOT the Postgres data volume — do not ignore it. The Postgres bind mount goes to `db_stack/db_data/` (created by P0-4).
  - Verify: File exists and listed patterns are ignored.

- [ ] **P0-7** Run `uv init` to create `pyproject.toml` with `requires-python = ">=3.14"`. Run `uv python install 3.14`.
  - Verify: `uv run python -c "import uuid; print(uuid.uuid7())"` succeeds.

- [ ] **P0-8** Add migration baseline using a simple custom SQL runner: create `db_stack/migrations/` directory with numbered SQL files (e.g., `0001_initial_schema.sql`). Create a `schema_migrations` table to track applied migrations. Add a `uv run uam migrate` CLI subcommand that applies all pending migrations in order. (Alembic or Flyway may replace this once confirmed they handle pgvector + AGE + pg_cron cleanly.)
  - Verify: Initial migration can be applied to a fresh DB; `schema_migrations` table records the applied file name and timestamp; re-running is idempotent.

---

## Phase 1a: Database Schema

- [ ] **P1a-1** Create `db_stack/schema.sql` defining the AGE graph `uam` with vertex labels `Session`, `Event`, `Memory` and edge labels `NEXT_EVENT`, `HAS_EVENT`, `REMEMBERS`.
  - Verify: After running against the DB, `SELECT * FROM ag_catalog.ag_graph` shows the `uam` graph.

- [ ] **P1a-1b** Create `db_stack/schema.sql` section for append-only `uam.events` relational source-of-truth table with raw payload + normalized fields.
  - Verify: `\d uam.events` shows columns including `raw_payload JSONB NOT NULL`, `payload_schema_version`, and timestamp fields.

- [ ] **P1a-2** Create `db_stack/schema.sql` section for the `uam.memories` table: `id UUID PK, path TEXT UNIQUE NOT NULL, frontmatter JSONB, content TEXT, embedding vector(768), created_at TIMESTAMPTZ, updated_at TIMESTAMPTZ`.
  - Verify: `\d uam.memories` shows all columns with correct types.

- [ ] **P1a-3** Create `db_stack/schema.sql` section for the `uam.embeddings` table: `id UUID PK, event_id UUID, embedding vector(768), content TEXT, metadata JSONB, created_at TIMESTAMPTZ`. Add an HNSW index on the embedding column (`CREATE INDEX ON uam.embeddings USING hnsw (embedding vector_cosine_ops)`). Apply the same HNSW index to `uam.memories.embedding`.
  - Verify: `\d uam.embeddings` shows all columns; `\di uam.*` shows the HNSW indexes.

- [ ] **P1a-4** Create `db_stack/schema.sql` section for the `uam.dream_runs` table: `id UUID PK, started_at TIMESTAMPTZ, completed_at TIMESTAMPTZ, events_processed INT, memories_updated INT, watermark TIMESTAMPTZ`.
  - Verify: `\d uam.dream_runs` shows all columns.

- [ ] **P1a-5** Create `db_stack/schema.sql` section for the `uam.search_cache` table: `query_hash TEXT PK, results JSONB, created_at TIMESTAMPTZ, ttl_seconds INT`.
  - Verify: `\d uam.search_cache` shows all columns.

- [ ] **P1a-6** Add GIN indexes for full-text search: `tsvector` column + GIN index on `uam.memories.content` and relational event content in `uam.events`.
  - Verify: `\di` shows the GIN indexes.

- [ ] **P1a-8** Add indexes for operational event queries on `uam.events` (`session_id`, `occurred_at`, `event_name`, and optional `client`).
  - Verify: `\di uam.*events*` shows expected btree indexes.

- [ ] **P1a-7** Add `db_stack/schema.sql` to docker-compose init (mount into `/docker-entrypoint-initdb.d/` after extension creation).
  - Verify: Fresh `docker compose up` creates all tables and the graph.

---

## Phase 1b: Core Python Library

- [ ] **P1b-0** Create `uam/__init__.py` and `uam/hooks/__init__.py` (empty, just making the packages importable).
  - Verify: `uv run python -c "import uam; import uam.hooks"` succeeds.

- [ ] **P1b-1** Create `uam/models.py` with Pydantic models: `HookEvent`, `Memory`, `SearchResult`, `DreamRun`, `SessionSummary`. `HookEvent.session_id` should be `Optional[UUID]` — if the harness doesn't supply one, the handler generates a UUID7 at ingest time and logs a warning.
  - Verify: `uv run python -c "from uam.models import HookEvent"` succeeds.

- [ ] **P1b-2** Create `uam/config.py` with settings (DB host/port/user/pass/db, Ollama URL, embedding model name) loaded from env vars with sensible defaults.
  - Verify: `uv run python -c "from uam.config import settings; print(settings.db_host)"` prints `localhost`.

- [ ] **P1b-3** Create `uam/db.py` with psycopg3 connection pool, a `get_connection()` context manager, and an `ensure_age()` helper that runs `LOAD 'age'; SET search_path = ag_catalog, "$user", public;`.
  - Verify: `uv run python -c "from uam.db import get_connection"` succeeds (import only; DB not required).

- [ ] **P1b-4** Create `uam/graph.py` with functions: `create_session()`, `create_event()`, `link_event()`, `get_session_events()`. All use AGE Cypher via raw SQL.
  - Verify: Unit test creates a session and two linked events, then retrieves them in order.

- [ ] **P1b-5** Create `uam/embeddings.py` with an abstract `EmbeddingProvider` base class and an `OllamaEmbeddingProvider` implementation that calls `POST /api/embed` on the Ollama endpoint.
  - Verify: With Ollama running, `uv run python -c "from uam.embeddings import OllamaEmbeddingProvider; p = OllamaEmbeddingProvider(); print(len(p.embed('hello')))"` prints `768`.

- [ ] **P1b-6** Create `uam/vectors.py` with functions: `store_embedding()`, `search_similar(query_embedding, limit)` using pgvector `<=>` operator.
  - Verify: Unit test stores an embedding and retrieves it via similarity search.

- [ ] **P1b-7** Create `uam/memories.py` with CRUD: `upsert_memory(path, frontmatter, content)`, `get_memory(path)`, `delete_memory(path)`, `list_memories(prefix)`. Upsert re-embeds on content change.
  - Verify: Unit test creates, reads, updates, and deletes a memory.

- [ ] **P1b-8** Create `uam/events.py` with `log_event(hook_event: HookEvent)` that: (1) writes raw payload + normalized fields to `uam.events` (relational source of truth, append-only), (2) projects the event to the AGE graph via `uam/projection.py`, (3) stores an embedding in `uam.embeddings`. Write order is relational first so partial failures don't lose data. Hook callers wrap `log_event()` in try/except — on any error, log and return without raising so the agent session is never blocked.
  - Verify: Unit test logs an event and confirms it appears in `uam.events`, the AGE graph, and `uam.embeddings`.

- [ ] **P1b-11** Create `uam/projection.py` with routines to project relational events to AGE nodes/edges (`Session`, `Event`, `NEXT_EVENT`, `HAS_EVENT`).
  - Verify: Unit test replays relational events and produces expected graph topology.

- [ ] **P1b-9** Create `uam/cli.py` with Click/Typer CLI exposing subcommands: `search`, `store`, `get`, `delete`, `list`, `sessions`, `dream`.
  - Verify: `uv run python -m uam.cli --help` shows all subcommands.

---

## Phase 2: Hook System

- [ ] **P2-0** Define and document the per-harness hook stdout injection format before implementing the injector. Each harness expects a different JSON shape on stdout from injection hooks (`SessionStart`, `UserPromptSubmit`). Document the exact expected format for each client in `hooks/<client>/README.md` or inline in `uam/hooks/injector.py`. Claude Code expects `{"system": "..."}` (prepended to system prompt) or `{"userPrompt": "..."}` (appended to user message). Confirm equivalent formats for Codex and Copilot before writing their configs.
  - Verify: Format spec exists and is referenced by P2-2 and P2-3.

- [ ] **P2-1** Create `uam/hooks/handler.py` that reads JSON from stdin, accepts `--client` flag (claude-code, codex, copilot), normalizes payload into `HookEvent`, and calls `log_event()`. Wrap the entire handler in try/except — on any error, write a structured log entry (timestamp, client, event_name, error message) to a local log file and exit 0 so the agent session is never blocked. If `session_id` is absent from the payload, generate a UUID7 and log a warning.
  - Verify: `echo '{...}' | uv run python -m uam.hooks.handler --client claude-code` logs the event without error; a payload that triggers an exception exits 0 and writes to the log file.

- [ ] **P2-2** Create `uam/hooks/injector.py` with functions for `SessionStart` (load profile memories) and `UserPromptSubmit` (vector search for relevant memories). Returns JSON on stdout.
  - Verify: Unit test with seeded memories returns expected JSON output.

- [ ] **P2-7** Add hook instrumentation for latency/error metrics (local logs with p50/p95 summaries by event type).
  - Verify: Running sample hook calls emits timing metrics and aggregated summary output.

- [ ] **P2-3** Create Claude Code hook config template at `hooks/claude-code/settings.json` with `SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `Stop`, `SessionEnd` entries.
  - Verify: JSON is valid and references correct handler paths.

- [ ] **P2-4** Create Codex hook config template at `hooks/codex/hooks.json` with equivalent events.
  - Verify: JSON is valid.

- [ ] **P2-5** Create GitHub Copilot hook config template at `hooks/copilot/hooks.json` with `sessionStart`, `userPromptSubmitted`, `preToolUse`, `postToolUse`, `agentStop`, `sessionEnd`.
  - Verify: JSON is valid.

- [ ] **P2-6** Create Warp skill at `hooks/warp/uam-memory/SKILL.md` instructing the agent to use `uam.cli` commands for memory operations.
  - Verify: File has valid YAML frontmatter with `name` and `description`.

---

## Phase 3: Dream Phase

- [ ] **P3-0** Define the dream phase output format before writing the prompt template or parser. The model must delimit multiple memory files in a single response in a machine-parseable way. Proposed format: each memory is a fenced block with the semantic path in the fence label, e.g. ` ```memory path/to/file.md ` followed by YAML frontmatter + content, then closing fence. Document this format in `uam/dream.py` docstring or a `docs/dream-output-format.md`. The parser in P3-2 will split on these fences.
  - Verify: Format spec is written; P3-2 and P3-3 reference it.

- [ ] **P3-1** Create abstract `LLMProvider` base class in `uam/llm.py` with `generate(prompt, system) -> str`. Implement `OllamaLLMProvider`. Dream model is selected by benchmarking starting with the smallest available (e.g., SmolLM3); the provider class must accept a configurable model name so benchmarking swaps are config-only.
  - Verify: With Ollama running, a simple prompt returns a non-empty string.
  - Verify: With Ollama running, a simple prompt returns a non-empty string.

- [ ] **P3-2** Create `uam/dream.py` with `run_dream()`: fetch events since last watermark, build prompt with current memories, call LLM, parse output into memory upserts.
  - Verify: Unit test with mocked LLM produces expected memory upserts.

- [ ] **P3-3** Create dream phase prompt template that instructs the model to output memories as markdown with YAML frontmatter at semantic paths, merging with existing memories.
  - Verify: Prompt template exists and includes merge/overwrite instructions.

- [ ] **P3-4** Wire `dream` CLI subcommand: check if DB stack is running (docker compose ps), start it if not (docker compose up -d), run dream phase, report results.
  - Verify: `uv run python -m uam.cli dream` runs end-to-end (with Ollama and DB available).

- [ ] **P3-5** After dream phase completes, invalidate search cache (truncate `uam.search_cache`).
  - Verify: Cache table is empty after a dream run.

- [ ] **P3-6** Add pg_cron smoke test task to verify extension availability and successful execution of a harmless scheduled SQL command.
  - Verify: Smoke test shows job execution in pg_cron metadata tables.

- [ ] **P3-7** Document dream scheduling policy as deferred in v1; add config placeholders only (no fixed schedule required).
  - Verify: README/IMPLEMENTATION note exists and CLI runs without requiring pg_cron schedule setup.

---

## Phase 4: Search

- [ ] **P4-1** Create `uam/search.py` with `hybrid_search(query, scope, limit)` combining vector search and full-text search results.
  - Verify: Unit test with seeded data returns results from both vector and FTS.

- [ ] **P4-2** Implement Reciprocal Rank Fusion (RRF) reranking in `uam/search.py` to merge vector and FTS result lists.
  - Verify: Unit test confirms merged ranking differs from either individual ranking.

- [ ] **P4-3** Implement search caching: before searching, check `uam.search_cache` by query hash (filtering out rows where `now() > created_at + ttl_seconds * interval '1 second'`); after searching, store results with TTL. TTL enforcement is at read time — expired rows are skipped on lookup and pruned lazily (delete where expired) on each cache write. Dream phase completion truncates the whole table (P3-5 already covers this).
  - Verify: Second identical search returns cached results; an expired entry (ttl elapsed) is treated as a miss; table is pruned on write.

- [ ] **P4-4** Wire `search` CLI subcommand with options: `--scope` (events|memories|all), `--limit`, query string.
  - Verify: `uv run python -m uam.cli search "test query"` returns formatted results.

---

## Phase 5: MCP Server

Note: Warp stays CLI-skill based in v1. MCP remains for compatible harnesses and tools.

- [ ] **P5-1** Create `uam/mcp_server.py` using the MCP Python SDK with tool definitions: `uam_search`, `uam_store`, `uam_get`, `uam_delete`, `uam_list`, `uam_sessions`.
  - Verify: `uv run python -m uam.mcp_server` starts without error and responds to MCP handshake.

- [ ] **P5-2** Wire each MCP tool to the corresponding core library function.
  - Verify: MCP client test calls `uam_store` then `uam_get` and receives the stored memory.

- [ ] **P5-3** Add MCP server entry point to `pyproject.toml` so it can be referenced by harness configs.
  - Verify: Entry point is listed in `pyproject.toml`.

---

## Phase 6: API & Web Interface

- [ ] **P6-1** Create `uam/api.py` with FastAPI app exposing REST endpoints: `GET/POST /memories`, `GET/DELETE /memories/{path}`, `GET /search`, `GET /sessions`, `GET /sessions/{id}/events`, `GET /stats`.
  - Verify: `uv run uvicorn uam.api:app` starts; `GET /stats` returns JSON.

- [ ] **P6-2** Initialize React frontend with Vite in `frontend/`: `npm create vite@latest frontend -- --template react-ts`.
  - Verify: `npm run dev` in `frontend/` serves the app on localhost.

- [ ] **P6-3** Build search page component with query input, scope selector, and results display.
  - Verify: Searching via the UI returns and displays results from the API.

- [ ] **P6-4** Build memory browser component with tree view of semantic paths and content viewer.
  - Verify: Navigating the tree shows memory content with frontmatter.

- [ ] **P6-5** Build session browser component with session list and event timeline.
  - Verify: Clicking a session shows its events in chronological order.

- [ ] **P6-6** Build stats dashboard component showing event counts, memory counts, and dream phase history.
  - Verify: Dashboard renders with data from the `/stats` endpoint.

---

## Phase 7: Testing & Documentation

- [ ] **P7-1** Set up `pytest` with a `conftest.py` that provides a test Postgres connection (via testcontainers or docker-compose test profile).
  - Verify: `uv run pytest --co` collects tests without error.

- [ ] **P7-2** Write unit tests for `uam/graph.py` (session/event CRUD).
  - Verify: `uv run pytest tests/test_graph.py` passes.

- [ ] **P7-3** Write unit tests for `uam/memories.py` (CRUD + embedding update).
  - Verify: `uv run pytest tests/test_memories.py` passes.

- [ ] **P7-4** Write unit tests for `uam/search.py` (hybrid search + RRF + caching).
  - Verify: `uv run pytest tests/test_search.py` passes.

- [ ] **P7-5** Write unit tests for `uam/hooks/handler.py` (payload normalization for each client).
  - Verify: `uv run pytest tests/test_hooks.py` passes.

- [ ] **P7-6** Write unit tests for `uam/dream.py` (with mocked LLM).
  - Verify: `uv run pytest tests/test_dream.py` passes.

- [ ] **P7-7** Update `README.md` with project overview, setup instructions, usage examples.
  - Verify: README contains sections for Setup, Usage, Hook Installation, and Dream Phase.

- [ ] **P7-8** Update `IMPLEMENTATION.md` with architecture diagram, schema details, and design decisions.
  - Verify: IMPLEMENTATION.md contains architecture overview and schema documentation.

- [ ] **P7-9** Add local bootstrap integration smoke test: fresh startup, schema init, one event log, one search, one dream run dry pass.
  - Verify: Single command or documented sequence passes on a clean local setup.
