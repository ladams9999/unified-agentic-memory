# Unified Agentic Memory (UAM)

UAM is a local-first shared memory layer for multiple coding harnesses (Claude Code, GitHub Copilot CLI, Codex, Warp). It captures hook events from each harness, stores them in Postgres, projects them into Apache AGE, indexes them for hybrid search, and runs a dream phase that distills recent activity into durable semantic memory files. Relevant memories are injected back into sessions automatically on start and on each user prompt.

## Documentation

- **AGENTS.md** — this file; project overview for agents starting cold
- **CLAUDE.md** — refers to AGENTS.md
- **PROJECT_PLAN.md** — goals and design decisions for the current project phase
- **IMPLEMENTATION.md** — architecture details, schema, and design rationale
- **PENDING_TASKS.md** — open tasks (runtime validation, cleanup)
- **COMPLETED_TASKS.md** — finished and verified tasks
- **README.md** — human-readable setup, usage, and hook installation guide

## Architecture

```
Harness hooks → uam.hooks.handler → uam.event_queue.enqueue_event
                                        ├── local SQLite queue (`state/uam.sqlite3`)
                                        └── background uam.event_processor.process_queued_events
                                              ├── uam.events       (Postgres relational, append-only)
                                              ├── Apache AGE graph (projected from relational rows)
                                              └── uam.embeddings   (pgvector; provider: Ollama | OpenAI)

CLI / API / MCP / Hook injector → uam.search.hybrid_search
                                        ├── vector search    (pgvector HNSW)
                                        ├── full-text search (GIN tsvector)
                                        └── uam.search_cache (TTL cache, cleared on dream)

Hook injector → uam.response_cache
                                        └── cached session-start / user-prompt payloads refreshed after queue processing

Dream phase → uam.dream.run_dream → LLM provider → memory blocks → uam.memories.upsert_memory
                                        (provider: Ollama | OpenAI | OpenRouter)
```

Hook handlers are deterministic and model-free. They always exit `0`; they queue events locally first so a dead database never blocks a session.

## Key source files

| Path | Purpose |
|---|---|
| `src/uam/models.py` | Pydantic models: events, memories, search results, dream runs |
| `src/uam/config.py` | `pydantic-settings` env-backed settings; provider selection via `UAM_EMBEDDING_PROVIDER` / `UAM_LLM_PROVIDER` |
| `src/uam/profiles.py` | Named runtime profiles and default profile resolution |
| `src/uam/db.py` | psycopg pool, AGE setup, migration runner |
| `src/uam/event_queue.py` | Durable local queue for normalized hook events |
| `src/uam/event_processor.py` | Async queue draining into relational ingest |
| `src/uam/events.py` | Append-only relational ingest + AGE projection + embedding |
| `src/uam/graph.py` | Apache AGE Cypher helpers |
| `src/uam/projection.py` | Relational-to-graph projection and replay |
| `src/uam/memories.py` | Semantic memory CRUD |
| `src/uam/response_cache.py` | Local cached hook responses |
| `src/uam/vectors.py` | Embedding persistence and similarity search |
| `src/uam/search.py` | Hybrid search, RRF reranking, cache management |
| `src/uam/dream.py` | Dream prompt, parsing, watermarking, cache invalidation |
| `src/uam/hooks/handler.py` | Hook event normalization, logging, injection output |
| `src/uam/hooks/injector.py` | Profile and search injection payloads |
| `src/uam/api.py` | FastAPI service (9 endpoints) |
| `src/uam/mcp_server.py` | FastMCP server (8 tools) |
| `src/uam/cli.py` | Typer CLI (`search`, `store`, `get`, `delete`, `list`, `confirm-idea`, `sessions`, `dream`, `migrate`, `install-hooks`, `profiles`, `save-profile`, `set-default-profile`, `queue-status`, `process-events`, `check-providers`) |
| `db_stack/Dockerfile_pguam18.4` | Custom Postgres 18 image with pgvector, Apache AGE, pg_cron |
| `db_stack/docker-compose.yml` | Compose stack; binds `db_stack/db_data/` as data dir |
| `db_stack/schema.sql` | Full schema: tables, indexes, AGE graph, triggers |
| `db_stack/migrations/0001_initial_schema.sql` | Versioned baseline migration |
| `hooks/claude-code/settings.json` | Claude Code hook config template |
| `hooks/copilot/hooks.json` | GitHub Copilot CLI hook config template |
| `hooks/codex/hooks.json` | Codex hook config template |
| `hooks/warp/uam-memory/SKILL.md` | Warp skill (v1: CLI-only, no MCP) |

## Database schema (uam schema in Postgres)

- `uam.events` — append-only source of truth; raw payload in `raw_payload JSONB` + normalized columns + `tsvector` FTS column
- `uam.memories` — semantic path, frontmatter, content, optional embedding, `tsvector` FTS column
- `uam.embeddings` — event embeddings + metadata + HNSW vector index
- `uam.dream_runs` — dream watermarks and bookkeeping
- `uam.search_cache` — cached hybrid search results with TTL
- `uam.schema_migrations` — applied migration tracking

AGE graph `uam`: vertices `Session`, `Event`, `Directory`, `Memory`; edges `HAS_EVENT`, `NEXT_EVENT`, `CHILD`.

## Running the stack

Prerequisites: `uv`, Docker Desktop, Node.js, Ollama with `nomic-embed-text` pulled (or set `UAM_EMBEDDING_PROVIDER=openai` / `UAM_LLM_PROVIDER=openai|openrouter` and provide API keys).

```bash
# 1. Start the database
cd db_stack
docker build -t pguam:18.4 -f Dockerfile_pguam18.4 .
docker compose up -d db
cd ..

# 2. Install Python deps and apply schema
uv sync --dev
uv run uam migrate

# 3. Start the API (optional)
uv run uvicorn uam.api:app --reload

# 4. Start the frontend (optional)
cd frontend && npm install && npm run dev

# 5. Start the MCP server (optional)
uv run python -m uam.mcp_server
```

Copy `db_stack/.env.example` to `db_stack/.env` and adjust credentials if needed before step 1.

## Hook deployment

Install hooks in `.claude/settings.json` (Claude Code) or `.github/hooks/uam-memory.json` (Copilot CLI) in the **observed project**, not in this repository. See `README.md` for the full config blocks and Windows-specific path-quoting notes.

Injection contract:
- Claude Code / Codex `SessionStart` → `{"system": "..."}` (profile memories)
- Claude Code / Codex `UserPromptSubmit` → `{"userPrompt": "..."}` (search results)
- Copilot CLI `sessionStart` → `{"additionalContext": "..."}` (profile memories)

## Dream phase

`uv run uam dream` reads events since the last watermark, sends them with current memories to the configured LLM (Ollama by default; set `UAM_LLM_PROVIDER=openai|openrouter`), parses fenced ` ```memory path.md ``` ` blocks, upserts memories, and clears search cache. `--dry-run` skips writes. Scheduling via `pg_cron` is installed but deferred in v1. Use `uv run uam check-providers` to validate the configured providers.

## Testing

`uv run pytest` — all tests are unit tests using fake connections and stubbed LLM calls. Runtime validation (Docker + Ollama required) is tracked separately in `PENDING_TASKS.md`.
