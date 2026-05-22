# Unified Agentic Memory repository instructions

## Build, test, and verification commands

- Python environment: `uv sync --dev`
- Backend tests: `uv run pytest`
- Single test file: `uv run pytest tests/test_search.py`
- Frontend build: `Set-Location frontend; npm run build`
- Frontend lint: `Set-Location frontend; npm run lint`
- Start local API: `uv run uvicorn uam.api:app --host 127.0.0.1 --port 8000`
- Apply DB migrations: `uv run uam migrate`
- Start the local Postgres stack: `Set-Location db_stack; docker compose up -d db`

For full local verification, run the Python tests and frontend build first, then bring up Docker and run the DB-backed flows (`uv run uam migrate`, `uv run uam search ...`, API checks, hook smoke tests, and dream runs).

## High-level architecture

- `src/uam/events.py` is the central ingest path: hook payloads are normalized into `HookEvent`, written to `uam.events`, projected into Apache AGE, and embedded into `uam.embeddings`.
- `src/uam/search.py` performs hybrid retrieval by combining pgvector similarity search (`src/uam/vectors.py`) with Postgres full-text search over `content_tsv`, then merges results with Reciprocal Rank Fusion and caches them in `uam.search_cache`.
- `src/uam/dream.py` reads events since the previous watermark, calls the configured Ollama model, parses fenced `memory` blocks, upserts them through `src/uam/memories.py`, and records the run in `uam.dream_runs`.
- The same core library is exposed through multiple surfaces:
  - CLI in `src/uam/cli.py`
  - FastAPI app in `src/uam/api.py`
  - MCP server in `src/uam/mcp_server.py`
  - harness hooks in `src/uam/hooks/`
- The frontend in `frontend/` is a thin Vite/React client for `/stats`, `/search`, `/memories`, `/sessions`, and `/sessions/{id}/events`.

## Key repository conventions

- Target **Python 3.13**. UUID7 generation uses `uuid6.uuid7()`; do not reintroduce `uuid.uuid7()` or Python 3.14-only compatibility code.
- Postgres init is sensitive to repo-specific setup in `db_stack/`:
  - keep `docker-compose.yml` using `PGDATA: /var/lib/postgresql/data`
  - keep the compose project name unique (`unified-agentic-memory-db`) to avoid collisions in shared Docker environments
  - create pg_cron through `db_stack/create_pgcron.sql`, not a shell init script
  - load AGE and set `search_path = ag_catalog, \"$user\", public` before graph creation
- Full-text search is implemented with trigger-maintained `content_tsv` columns in `uam.events` and `uam.memories`; do not switch back to generated columns or expression indexes without revalidating Postgres immutability rules.
- Psycopg JSON/vector writes need explicit adapters:
  - use `psycopg.types.json.Jsonb(...)` for JSONB inserts/updates
  - use `pgvector.Vector(...)` for vector similarity query parameters
- Dream runs depend on a live Ollama model. `src/uam/config.py` defaults to `smollm3`, but local verification may require overriding `UAM_LLM_MODEL` to an installed model. Respect `llm_timeout_seconds` for slower local models.
- Hook handlers must remain non-blocking: they log failures locally and still exit `0` so harness sessions are not interrupted.
