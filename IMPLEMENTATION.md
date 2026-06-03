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
  - `models.py`: Pydantic models for events, memories, search results, and dream runs
  - `config.py`: `pydantic-settings` environment-backed settings
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
  - `cli.py`: Typer CLI (`search`, `store`, `get`, `delete`, `list`, `confirm-idea`, `sessions`, `dream`, `migrate`, `install-hooks`, `check-providers`)

## Database schema

`db_stack/migrations/` defines all schema changes:

- `0001_initial_schema.sql`
  - `uam.events`: append-only source of truth; raw payload in `raw_payload JSONB`; normalized columns for session, client, model, tool, prompt, cwd, and timestamps; generated `tsvector` for full-text search
  - `uam.memories`: semantic path, frontmatter, content, optional embedding, timestamps; generated `tsvector` for full-text search
  - `uam.embeddings`: event embeddings plus metadata; HNSW vector index
  - `uam.dream_runs`: dream bookkeeping and watermarking
  - `uam.search_cache`: cached hybrid search results with TTL
  - `uam.schema_migrations`: applied migration tracking
- `0002_age_graph.sql`
  - Creates the Apache AGE graph `uam`; skipped automatically by the migration runner when AGE is not installed (e.g. Supabase)
  - Creates the Apache AGE graph `uam`; skipped automatically by the migration runner when AGE is not installed (e.g. Supabase)

Apache AGE graph `uam` uses labels:

- vertices: `Session`, `Event`, `Directory`, `Memory`
- edges: `HAS_EVENT`, `NEXT_EVENT`, `CHILD`

`Directory` and `Memory` nodes in the graph store only `{id, path}` — references to relational rows, not copies of content. Path hierarchy is represented structurally: a memory at `profiles/user/prefs` produces `profiles`, `profiles/user`, and `profiles/user/prefs` nodes linked by `:CHILD` edges, mimicking a markdown directory tree. On delete, orphaned `Directory` nodes are pruned bottom-up.

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
4. Ask the LLM to emit fenced `memory` blocks, each with a `type:` frontmatter field (`fact`, `learning`, or `idea`).
5. Parse each block into `(path, frontmatter, content, memory_type)`.
6. Upsert memories (silently skips any block that tries to overwrite a `fact`) and clear search cache.
7. Record the run in `uam.dream_runs`.

### Memory types

- `fact` — a specific, sourced, static observation. Created once; no update path is exposed anywhere (MCP, API, CLI, or dream phase).
- `learning` — a synthesized conclusion from multiple facts. Updatable by the dream phase or via `uam_store`.
- `idea` — a probable but unconfirmed inference. Updatable; promoted to `learning` via `confirm_idea()` / `uam_confirm_idea` MCP tool / `uam confirm-idea` CLI command.

Scheduling policy is deferred in v1. `pg_cron` is installed so scheduling can be added without changing the core runtime model.

### LLM and embedding provider selection

The provider is selected via `UAM_LLM_PROVIDER` (`ollama` | `openai` | `openrouter`) and `UAM_EMBEDDING_PROVIDER` (`ollama` | `openai`). Both default to `ollama`.

**Ollama (default):** `UAM_LLM_MODEL=mistral` (Mistral 7B). `phi4-mini` was evaluated but discarded: it enters a repetitive-token loop on structured-output prompts that require fenced ` ```memory ``` ` blocks. `mistral` follows the format reliably. `phi4-mini-reasoning` is available but untested.

**OpenAI:** `UAM_OPENAI_LLM_MODEL=gpt-4o-mini` (default). Embedding model defaults to `text-embedding-3-small` with `dimensions=768` to match the existing pgvector schema — no migration required.

**OpenRouter:** `UAM_OPENROUTER_LLM_MODEL=mistralai/mistral-7b-instruct` (default). OpenRouter does not expose an embeddings endpoint; use `UAM_EMBEDDING_PROVIDER=openai` alongside `UAM_LLM_PROVIDER=openrouter`.

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

## Claude Code integration

### Hook config format

Claude Code expects hook entries as an array of objects, each with a `hooks` array containing `{"type": "command", "command": "..."}` entries. The original template at `hooks/claude-code/settings.json` used a flat string value per event (`"SessionStart": "command"`) which Claude Code silently ignores. It was rewritten to the correct nested format:

```json
"SessionStart": [
  {"hooks": [{"type": "command", "command": "uv run ..."}]}
]
```

### Windows path quoting

The hook command uses `uv run --directory <path>` to run the handler from any working directory. On Windows, when Claude Code passes the command string to the shell (bash / Git Bash), unquoted backslash paths are mangled — `C:\Users\lloyd` becomes `C:Userslloyd` because bash treats `\U` and `\l` as escape sequences and strips the backslash.

The fix is to wrap the path in double-quotes inside the command string. In JSON this is represented as `\"`:

```json
"command": "uv run --directory \"C:\\Users\\lloyd\\unified-agentic-memory\" python -m uam.hooks.handler --client claude-code"
```

Verified: unquoted path produces `os error 2` (file not found); quoted path runs correctly.

### Injector wiring

`src/uam/hooks/injector.py` defines two functions that were not called anywhere before this work:

- `session_start_payload(client)` — loads `profiles/` memories and returns `{"system": "<content>"}` for injection into the Claude Code system prompt.
- `user_prompt_payload(client, query)` — runs hybrid search against the query and returns `{"userPrompt": "<results>"}` for injection before the user message.

`src/uam/hooks/handler.py` was updated to call these after `log_event`:

```python
if event.event_name == "SessionStart":
    injection = session_start_payload(args.client)
elif event.event_name == "UserPromptSubmit" and event.user_prompt:
    injection = user_prompt_payload(args.client, event.user_prompt)
if injection is not None:
    print(json.dumps(injection))
```

Injection failures are caught separately from the logging path so a bad DB connection cannot suppress the `{"system": ...}` or `{"userPrompt": ...}` response from a cached or previously-working call. Both paths exit `0` regardless.

### Deployment architecture

Hooks in this repository's `.claude/settings.json` would capture UAM's own development activity, polluting the event store with tool calls made while building UAM. The correct deployment is:

1. UAM project open in one Claude Code window — no hooks, DB running in background.
2. Observed project open in a second window — `.claude/settings.json` contains the hook entries pointing at UAM's handler.

This is documented in the README's "Installing in Claude Code" section.

### Verification results

All six hook event types (`SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `Stop`, `SessionEnd`) were tested by piping representative Claude Code payloads to the handler. All exit `0`. Malformed JSON and empty stdin also exit `0`. Errors are written to `logs/hook-handler.log`.

Injection output (`{"system": ...}` and `{"userPrompt": ...}`) requires a live database and stored memories. With the DB unreachable, injection silently fails and the handler still exits `0` with no stdout — Claude Code proceeds normally with no injected context.

## GitHub Copilot CLI integration

### Hook config format

GitHub Copilot CLI expects repository hook files under `.github/hooks/*.json`, with top-level `"version": 1` and each event mapped to an array of hook objects. The original template at `hooks/copilot/hooks.json` used flat string values per event and omitted the version field, so it did not match Copilot's documented schema.

The corrected template uses command hook objects:

```json
"sessionStart": [
  {
    "type": "command",
    "powershell": "uv run python -m uam.hooks.handler --client copilot",
    "cwd": "<UAM_PROJECT_DIR>",
    "timeoutSec": 30
  }
]
```

### Deployment path

Unlike the Claude Code template, Copilot CLI supports a `cwd` field directly in the hook definition. That lets the observed project keep a short command string while still executing inside the UAM repository's virtual environment. The observed project only needs `.github/hooks/uam-memory.json`; it does not need UAM installed as one of its own dependencies.

For the sibling-project setup used during development, the hook file belongs in the observed repository (`..\docling-converter\.github\hooks\uam-memory.json`) and points `cwd` back to the UAM repository.

### Payload normalization changes

Copilot CLI delivers a different payload shape from Claude Code:

- camelCase event names such as `sessionStart`, `userPromptSubmitted`, and `agentStop`
- `hook_event_name` / `sessionId` rather than only `eventName`
- top-level `toolName` / `toolArgs` fields instead of a nested `tool` object
- millisecond Unix timestamps instead of only ISO 8601 strings

`src/uam/hooks/handler.py` now normalizes all of these into the same canonical event names used elsewhere in the project (`SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `Stop`, and so on). This keeps the relational event store and downstream processing consistent across harnesses.

### Injection semantics

Copilot CLI does not use the same stdout contract as Claude Code. Instead:

- `sessionStart` can inject context with `{"additionalContext": "..."}`.
- `userPromptSubmitted` is logged, but Copilot ignores stdout for that event.

The handler now branches on `--client copilot` and converts `session_start_payload()` from the internal `{"system": ...}` format into Copilot's `{"additionalContext": ...}` output. Other clients keep their existing `{"system": ...}` and `{"userPrompt": ...}` behavior.

### Verification results

Copilot session-start payloads were validated with the documented hook schema, including millisecond timestamps and top-level `toolName` / `toolArgs` fields. The handler now emits `{"additionalContext": ...}` for Copilot `sessionStart`, still exits `0` on failures, and continues writing errors to `logs/hook-handler.log`.

## Python runtime note

The project targets Python 3.13. UUID7 generation is provided through the `uuid6` package, which keeps the codebase off Python 3.14 beta-specific runtime behavior and avoids the compatibility shim that was temporarily needed for FastAPI and MCP imports.
