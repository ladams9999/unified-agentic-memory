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
- [x] **P0-7** Initialize the `uv` project, pin Python 3.14, and verify `uuid.uuid7()`.

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

## Phase 7: Testing & Documentation

- [x] **P7-1** Set up `pytest` collection and a local fake-connection testing approach.
- [x] **P7-2** Write graph unit tests.
- [x] **P7-3** Write memory CRUD unit tests.
- [x] **P7-4** Write search unit tests.
- [x] **P7-5** Write hook handler unit tests.
- [x] **P7-6** Write dream phase unit tests.
- [x] **P7-7** Update `README.md` with setup, usage, hook installation, and dream phase sections.
- [x] **P7-8** Update `IMPLEMENTATION.md` with architecture, schema, and design details.
