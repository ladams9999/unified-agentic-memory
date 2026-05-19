# Unified Agentic Memory

Unified Agentic Memory (UAM) is a local-first memory layer for multiple coding harnesses. It stores hook events relationally in Postgres, projects them into Apache AGE, indexes event and memory content for hybrid search, and runs a dream phase that turns recent activity into durable semantic memory files.

## Setup

1. Install `uv`, Docker Desktop, and Node.js.
2. Copy `db_stack/.env.example` to `db_stack/.env` and adjust credentials if needed.
3. Build and start the database stack from `db_stack/`.
4. Run `uv sync --dev`.
5. Apply schema migrations with `uv run uam migrate`.
6. Start the API with `uv run uvicorn uam.api:app --reload`.
7. Start the frontend with `cd frontend && npm install && npm run dev`.

Python is pinned to `>=3.13`. UUID7 generation comes from the `uuid6` package (`uuid6.uuid7()`), which avoids relying on Python 3.14-only stdlib support.

## Usage

### CLI

- `uv run uam migrate`
- `uv run uam store "topics/postgres.md" "Use pgvector and AGE." --frontmatter '{"title":"Postgres"}'`
- `uv run uam get "topics/postgres.md"`
- `uv run uam list "topics/"`
- `uv run uam search "pgvector age" --scope all --limit 5`
- `uv run uam sessions`
- `uv run uam dream --dry-run`

### API

The FastAPI app exposes:

- `GET /memories`
- `POST /memories`
- `GET /memories/{path}`
- `DELETE /memories/{path}`
- `GET /search`
- `GET /sessions`
- `GET /sessions/{id}/events`
- `GET /stats`
- `POST /dream`

### MCP

Start the MCP server with:

`uv run python -m uam.mcp_server`

The server exposes `uam_search`, `uam_store`, `uam_get`, `uam_delete`, `uam_list`, `uam_sessions`, and `uam_dream`.

## Hook Installation

Template hook configs live under `hooks/`:

- `hooks/claude-code/settings.json`
- `hooks/codex/hooks.json`
- `hooks/copilot/hooks.json`
- `hooks/warp/uam-memory/SKILL.md`

The shared injector contract is:

- `SessionStart` emits `{"system": "..."}`.
- `UserPromptSubmit` emits `{"userPrompt": "..."}`.

Hook handlers are deterministic and model-free. They normalize payloads, log events, capture latency metrics, and always exit `0` so agent sessions are not blocked on local failures.

## Dream Phase

The dream phase reads events since the last watermark, sends recent events plus current memories to an LLM, parses ` ```memory path.md ` blocks, upserts memories, and invalidates search cache. Scheduling is intentionally deferred in v1 even though `pg_cron` is installed and available.

The output format is:

````text
```memory semantic/path.md
---
title: Example
---
Durable note content
```
````

## Frontend

The Vite React frontend provides:

- hybrid search
- memory browsing by semantic path
- session timeline browsing
- stats cards for event, memory, and dream counts

Set `VITE_API_BASE` if the API is not running at `http://127.0.0.1:8000`.

## Local smoke sequence

For a quick manual smoke pass on a clean machine:

1. Start Docker Desktop.
2. `cd db_stack && docker build -t pguam:18.4 -f Dockerfile_pguam18.4 .`
3. `docker compose up -d db`
4. `cd .. && uv sync --dev`
5. `uv run uam migrate`
6. Pipe a sample hook payload into `uv run python -m uam.hooks.handler --client claude-code`
7. `uv run uam search "sample"`
8. `uv run uam dream --dry-run`
