# Unified Agentic Memory — Implementation Plan
## Problem Statement
Build a single, shared memory layer for coding agents across Claude Code, Codex, GitHub Copilot, and Warp. Hooks passively log events, a dream phase distills them into durable memories, and injection on session start / user prompt provides context to any harness. This differs from the reference article (which uses Neo4j) by using Postgres with pgvector + Apache AGE, adding full-text search, vector search, and a web UI.
## Current State
* **Database stack**: Docker-based Postgres 18 image (`pguam:18.4`) with pgvector, Apache AGE, pg_cron. Working setup copied from another running instance.
* **Directories**: `db_stack/` for Docker/DB config, `db_data/` for Postgres data volume, `uam_data/` reserved for potential markdown file archive.
* **Project docs**: Scaffolding only — no application code yet.
* **Python**: Target Python 3.14 via `uv`. This gives us built-in `uuid.uuid7()` (RFC 9562) — no third-party UUID package needed.
## Phase 0: Fixes & Project Init
1. **Dockerfile: TimescaleDB reference** — Remove `timescaledb` from `shared_preload_libraries`; keep only `pg_cron`.
2. **Dockerfile: AGE branch** — Pin to `PG18/v1.7.0-rc0` release tag with `--depth 1`.
3. **Dockerfile: pg_cron extension** — Add `CREATE EXTENSION IF NOT EXISTS pg_cron;` (note: pg_cron must be created in the `postgres` database, not `uam_db`).
4. **docker-compose.yml: volume** — Map Postgres data to `./db_data/` instead of a named volume. Keep `uam_data/` for the potential markdown file archive.
5. **.env handling** — Copy `.env` → `.env.example` (committed). Add `.env` to `.gitignore`. Remove `.env` from git tracking.
6. **PG image tag** — Trust existing `postgres:18.4` for now; fall back to an earlier 18.x if build fails.
7. **Project init** — `uv init` with `requires-python = ">=3.14"`, `uv python install 3.14`.
## Architecture Overview
```warp-runnable-command
┌──────────────────────────────────────────────────┐
│                  Harness Layer                   │
│  Claude Code │ Codex │ Copilot │ Warp (skill)   │
│     hooks    │ hooks │  hooks  │  MCP + skill    │
└──────┬───────┴───┬───┴────┬────┴───────┬─────────┘
       │           │        │            │
       ▼           ▼        ▼            ▼
┌──────────────────────────────────────────────────┐
│            UAM Python Core Library               │
│  Hook handler │ Event logger │ Memory manager    │
│  Search engine │ Dream phase │ MCP server        │
└──────────────────────┬───────────────────────────┘
                       │
       ┌───────────────┼───────────────┐
       ▼               ▼               ▼
  ┌─────────┐   ┌───────────┐   ┌───────────┐
  │ pgvector│   │Apache AGE │   │ Full-text  │
  │ vectors │   │  graph    │   │  search    │
  └─────────┘   └───────────┘   └───────────┘
              PostgreSQL 18 (pguam)
```
## Phase 1: Database Schema & Core Library
### 1a. Database Schema
* **Graph (AGE)**: Create a graph `uam` with vertex labels: `Session`, `Event`, `Memory`. Edge labels: `NEXT_EVENT` (linked list within session), `HAS_EVENT` (session → first event), `REMEMBERS` (session → memory references).
* **Vector table**: `uam.embeddings` — `id UUID PRIMARY KEY, event_id UUID, embedding vector(768), content TEXT, metadata JSONB, created_at TIMESTAMPTZ`.
* **Full-text search**: GIN index with `pg_trgm` + `tsvector` columns on event content and memory content.
* **Memories table**: `uam.memories` — `id UUID PRIMARY KEY, path TEXT UNIQUE NOT NULL, frontmatter JSONB, content TEXT, embedding vector(768), created_at TIMESTAMPTZ, updated_at TIMESTAMPTZ`. The `path` is the semantic wiki path (e.g., `profile/role.md`, `tools/bash/common-flags.md`). Memories mirror the markdown file archive concept from the article, but stored in DB rather than on disk. The `uam_data/` directory is reserved for a potential on-disk sync of these memories.
* **UUID7**: Use Python 3.14's built-in `uuid.uuid7()` — no third-party package needed.
### 1b. Core Python Library (`uam/`)
Structure:
```warp-runnable-command
uam/
  __init__.py
  config.py          # Settings, DB connection, Ollama endpoint
  db.py              # Postgres connection pool (asyncpg or psycopg3)
  graph.py           # AGE Cypher queries for session/event graph
  vectors.py         # pgvector operations (embed, store, search)
  search.py          # Hybrid search: vector + full-text + rerank
  memories.py        # CRUD for markdown memories
  events.py          # Event logging (hook payloads → graph + vectors)
  dream.py           # Dream phase batch job
  embeddings.py      # Ollama nomic-embed-text client
  models.py          # Pydantic models for events, memories, payloads
```
* Use `uv` for project management with `pyproject.toml`, `requires-python = ">=3.14"`.
* Use `psycopg[binary]` (psycopg3) for Postgres access — it supports both sync and async, and works well on Windows. AGE queries via raw SQL: `SELECT * FROM cypher('uam', $$ ... $$) AS (result agtype)`.
* Design all service interfaces (embeddings, LLM, DB) behind abstract base classes so non-local providers can be swapped in later without changing calling code.
## Phase 2: Hook System
### Hook contract (cross-harness)
All hooks are thin shell/Python scripts that:
1. Read JSON payload from stdin.
2. Normalize it into a common `HookEvent` schema (session_id, agent_name, model, event_name, tool_details, user_prompt, cwd, timestamp).
3. Call the UAM core library to log the event.
4. For injection hooks (`SessionStart`, `UserPromptSubmit`), query memories and emit JSON on stdout.
### Per-harness configuration
* **Claude Code**: `.claude/settings.json` with `hooks` block. Shell scripts call `python -m uam.hooks.handler --client claude-code`. Events: `SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `Stop`, `SessionEnd`.
* **Codex**: `.codex/hooks.json` or `config.toml` `[hooks]` tables. Same Python handler with `--client codex`. Events: `SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `Stop`.
* **GitHub Copilot**: `.github/hooks/*.json` with bash/powershell commands. Same handler with `--client copilot`. Events: `sessionStart`, `userPromptSubmitted`, `preToolUse`, `postToolUse`, `agentStop`, `sessionEnd`.
* **Warp**: No hook system. Build a Warp skill (SKILL.md) that instructs the agent to use CLI commands (`python -m uam.cli search`, `python -m uam.cli store`, etc.) directly via shell. This avoids the overhead of an MCP server and uses Warp's existing Bash tool — the skill tells the agent when and how to call the CLI. Note: skills are instructions consumed by the LLM, so they don't bypass LLM calls, but they avoid the need for a separate MCP server setup for Warp.
### Key design point
Hooks must be fast and deterministic — no LLM calls. They only log events and inject pre-computed memories. The `SessionStart` hook loads profile memories. The `UserPromptSubmit` hook runs a quick vector search for relevant memories and appends them.
## Phase 3: Dream Phase
* A CLI command (`python -m uam.dream`) and a pg_cron scheduled job.
* Reads all events since the last watermark (stored in a `uam.dream_runs` table).
* Sends events + current memory store to Ollama (local model, starting with the chosen small model).
* The model produces/updates markdown memories at semantic paths with YAML frontmatter.
* Memories are merged (not appended): if a path exists, the model rewrites it; if new info contradicts old, the old is updated.
* After writing, re-embed all changed memories.
* Update the watermark.
* Can also be triggered by `SessionEnd` hook where supported.
### Dream phase model concern
Small local models (7B-14B) may struggle with the merge/distill task. The plan starts local as requested. The LLM interface should be behind an abstract provider class so cloud APIs can be swapped in later — but no cloud-specific code will be written in the first pass. Prompt engineering for the dream phase will need careful iteration.
## Phase 4: Search
* **Vector search**: Embed query via Ollama, search `uam.embeddings` + `uam.memories` using pgvector `<=>` operator.
* **Full-text search**: `ts_query` against `tsvector` columns.
* **Hybrid**: Combine results, deduplicate by ID, rerank using Reciprocal Rank Fusion (RRF) or a simple score merge. Truncate to top-k.
* **Caching**: Cache search results keyed by query hash, invalidate on dream phase completion. Use a simple `uam.search_cache` table with TTL.
## Phase 5: MCP Server
Expose UAM as an MCP server so any harness (including Warp) can interact with memories:
* `uam_search(query, scope, limit)` — search events, memories, or both
* `uam_store(path, content, frontmatter)` — create/update a memory
* `uam_get(path)` — retrieve a specific memory
* `uam_delete(path)` — remove a memory
* `uam_list(prefix)` — list memories under a path prefix
* `uam_sessions(limit)` — list recent sessions
Use the MCP Python SDK (`mcp` package) to build a stdio-based server.
## Phase 6: API & Web Interface
* **API**: FastAPI app exposing the same operations as the MCP server plus session browsing and stats.
* **Web UI**: React frontend is a good fit here — the UI needs interactive tree views (memory browser), timeline visualization (session events), and real-time search. React's component model handles this well and the ecosystem (e.g., react-router, tanstack-query) is mature. Use Vite for build tooling. The API (FastAPI) serves as the backend.
    * Search with all options (scope, limit, type)
    * Memory browser (tree view of semantic paths)
    * Session browser (timeline of events per session)
    * Stats dashboard (event counts, memory counts, dream phase history)
## Phase 7: Testing & Documentation
* `pytest` for unit tests (as specified).
* Test fixtures with a test Postgres instance (use testcontainers or a dedicated docker-compose test profile).
* Update README.md with usage instructions.
* Update IMPLEMENTATION.md with architecture details.
## Parallelization Opportunities
Phases can be partially parallelized with child agents:
* **Agent A**: Phase 0 (Dockerfile fixes) + Phase 1a (DB schema + migrations) — independent infrastructure work.
* **Agent B**: Phase 1b (core Python library scaffolding) + Phase 2 (hook system) — can start once schema is defined.
* **Agent C**: Phase 3 (dream phase) — depends on core library and schema, but can be developed with stubs.
* **Agent D**: Phase 5 (MCP server) — depends on core library, can be developed in parallel with Phase 3.
Phases 4 (search), 6 (API/web), and 7 (testing) are more sequential and depend on the core library being functional.
The most effective split is **two parallel tracks** after Phase 0:
* Track 1: Schema → Core library → Hook system → Dream phase
* Track 2: (after core library stubs exist) MCP server → API → Web UI
## Resolved Decisions
* **Embedding model**: `nomic-embed-text` (768-dim vectors).
* **Memory path taxonomy**: Dream phase infers paths organically. The markdown wiki structure (paths, frontmatter, content) is replicated entirely in the `uam.memories` table — no filesystem-based memory store.
* **Dream phase scheduling**: A CLI entrypoint (`uv run uam dream`) that is self-contained: it starts the DB stack (docker compose up) if not running, runs the dream phase, and optionally shuts it down after. This script can be called from Windows Task Scheduler, a cron job, or a `SessionEnd` hook. No long-running scheduler process required.
