# Implementation

## Architecture overview

```text
Hooks -> uam.hooks.handler -> uam.events.log_event -> Postgres relational events
                                                -> Apache AGE projection
                                                -> pgvector embeddings

CLI / API / MCP / Hook injector -> uam.search.hybrid_search -> vector + FTS + cache

Dream phase -> uam.dream.run_dream -> LLM -> parsed memory blocks -> uam.memories.upsert_memory
```

## Runtime layout

- `src/uam/`
  - `models.py`: lightweight typed models with `model_dump` compatibility helpers
  - `config.py`: environment-backed settings
  - `db.py`: psycopg pool, AGE setup, migration runner
  - `events.py`: append-only relational ingest plus projection and embedding
  - `graph.py`: AGE Cypher helpers
  - `projection.py`: relational-to-graph projection
  - `memories.py`: semantic memory CRUD
  - `vectors.py`: embedding persistence and similarity search
  - `search.py`: hybrid search, RRF reranking, and cache management
  - `dream.py`: dream prompt creation, parsing, watermarking, and cache invalidation
  - `hooks/`: handler, injector, and latency metrics
  - `api.py`: FastAPI service
  - `mcp_server.py`: FastMCP server
  - `cli.py`: Typer CLI

## Database schema

`db_stack/schema.sql` and `db_stack/migrations/0001_initial_schema.sql` define:

- `uam.events`
  - append-only source of truth
  - raw payload stored losslessly in `raw_payload JSONB`
  - normalized columns for session, client, model, tool, prompt, cwd, and timestamps
  - generated `tsvector` column for full-text search
- `uam.memories`
  - semantic path, frontmatter, content, optional embedding, timestamps
  - generated `tsvector` column for full-text search
- `uam.embeddings`
  - event embeddings plus metadata
  - HNSW vector index
- `uam.dream_runs`
  - dream bookkeeping and watermarking
- `uam.search_cache`
  - cached hybrid search results with TTL
- `uam.schema_migrations`
  - applied migration tracking

Apache AGE graph `uam` is created alongside the schema and uses labels:

- vertices: `Session`, `Event`, `Memory`
- edges: `HAS_EVENT`, `NEXT_EVENT`, `REMEMBERS`

## Docker stack

The Postgres image is built from `db_stack/Dockerfile_pguam18.4` and includes:

- `pg_cron`
- `pgvector` pinned to `v0.8.2`
- Apache AGE pinned to `PG18/v1.7.0-rc0`

`docker-compose.yml` bind-mounts `db_stack/db_data/` as the Postgres data directory, mounts the extension init SQL, mounts a dedicated `create_pgcron.sh` for the `postgres` database, and mounts `schema.sql` for first-run initialization.

## Event ingest flow

1. A harness hook pipes JSON to `uam.hooks.handler`.
2. The handler normalizes client-specific payload shapes into a `HookEvent`.
3. `uam.events.log_event` writes the relational row first.
4. The event is projected into AGE.
5. An embedding is generated and stored in `uam.embeddings`.
6. Latency metrics are appended to `logs/hook_metrics.jsonl` and summarized to `logs/hook_metrics_summary.json`.

Failures are logged locally and the handler still exits `0`.

## Search design

`uam.search.hybrid_search()` does four things:

1. Hashes the search request and checks `uam.search_cache`.
2. Runs vector search against event embeddings and memory embeddings.
3. Runs full-text search against relational event content and memory content.
4. Merges ranked lists with Reciprocal Rank Fusion (RRF) and stores the merged result in cache.

Cache TTL is enforced on read and expired rows are pruned lazily on each cache write. Dream runs truncate the whole cache because new durable memories can invalidate relevance broadly.

## Dream phase design

The dream phase is intentionally simple and file-oriented:

1. Fetch events since the last dream watermark.
2. Load current memories.
3. Build a prompt that includes both.
4. Ask the LLM to emit fenced `memory` blocks.
5. Parse each block into `(path, frontmatter, content)`.
6. Upsert memories and clear search cache.
7. Record the run in `uam.dream_runs`.

Scheduling policy is deferred in v1. `pg_cron` is installed so scheduling can be added without changing the core runtime model.

## Frontend design

The frontend is a small Vite + React dashboard with four surfaces:

- stats cards from `/stats`
- hybrid search form using `/search`
- memory browser using `/memories`
- session browser and event timeline using `/sessions` and `/sessions/{id}/events`

It intentionally stays thin and delegates all ranking and persistence behavior to the backend.

## Testing approach

The test suite stays local and deterministic:

- graph projection behavior uses a fake Cypher runner
- memory CRUD uses a fake in-memory connection
- search tests stub vector search and cache persistence
- hook tests cover normalization and non-blocking error handling
- dream tests mock the LLM and memory upserts

This keeps unit coverage fast while leaving the README smoke sequence for full local Docker-backed verification.
