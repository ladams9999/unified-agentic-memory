# Unified Agentic Memory

Unified Agentic Memory (UAM) is a local-first memory layer for multiple coding harnesses. It stores hook events relationally in Postgres, projects them into Apache AGE, indexes event and memory content for hybrid search, and runs a dream phase that turns recent activity into durable semantic memory files.

## Platform support

| Harness | Windows | macOS | Linux |
|---|---|---|---|
| GitHub Copilot CLI | Tested | Expected | Expected |
| Claude Code | Tested | Expected | Expected |
| Codex | Expected | Expected | Expected |
| Warp | Expected | Expected | Expected |

"Tested" means the full hook flow has been validated end-to-end on that platform.
"Expected" means the code is written to be platform-neutral and should work, but has not yet been validated.

## Setup

### Prerequisites

Install `uv` (the Python package manager used throughout):

- **macOS / Linux** — `curl -Ls https://astral.sh/uv/install.sh | sh` or `brew install uv`
- **Windows** — `winget install --id=astral-sh.uv` or `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`

Also install Docker Desktop and Node.js.

### Steps

1. Copy `db_stack/.env.example` to `db_stack/.env` and adjust credentials if needed.
2. Build and start the database stack from `db_stack/`.
3. Run `uv sync --dev`.
4. Apply schema migrations with `uv run uam migrate`.
5. Start the API with `uv run uvicorn uam.api:app --reload`.
6. Start the frontend with `cd frontend && npm install && npm run dev`.

Python is pinned to `>=3.13`. UUID7 generation comes from the `uuid6` package (`uuid6.uuid7()`), which avoids relying on Python 3.14-only stdlib support.

## Using Supabase

Supabase provides a managed Postgres with pgvector but without Apache AGE. UAM supports this configuration: graph projection is disabled and all other features work normally.

### Enable pgvector

In the Supabase dashboard SQL editor:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### Configure environment variables

Set the following in `.env` (or export them directly):

```env
UAM_DB_HOST=<your-project>.supabase.co
UAM_DB_PORT=5432
UAM_DB_USER=postgres
UAM_DB_PASSWORD=<your-database-password>
UAM_DB_NAME=postgres
UAM_DB_SSLMODE=require
UAM_DISABLE_GRAPH=true
```

Replace `<your-project>` with your Supabase project reference and `<your-database-password>` with the password from the Supabase dashboard under **Settings → Database**.

### Apply migrations

```bash
uv run uam migrate
```

UAM will detect that AGE is not installed and skip the AGE migration (`0003_age_graph.sql`), printing a warning. All other migrations apply normally.

### Feature notes

- **Unavailable:** graph traversal (Session/Event graph nodes, `NEXT_EVENT` chains). Graph projection calls become no-ops.
- **Available:** event logging, semantic memory CRUD, hybrid search (vector + full-text), the dream phase, the MCP server, the session timeline browser (backed by relational events, not AGE), and all CLI and API commands.

## Usage

### CLI

- `uv run uam migrate`
- `uv run uam store "topics/postgres.md" "Use pgvector and AGE." --frontmatter '{"title":"Postgres"}'`
- `uv run uam get "topics/postgres.md"`
- `uv run uam delete "topics/postgres.md"`
- `uv run uam list "topics/"`
- `uv run uam search "pgvector age" --scope all --limit 5`
- `uv run uam sessions`
- `uv run uam dream`
- `uv run uam confirm-idea "topics/postgres.md"`
- `uv run uam profiles`
- `uv run uam save-profile focused --memory-prefix profiles/focused`
- `uv run uam set-default-profile focused`
- `uv run uam queue-status`
- `uv run uam process-events --limit 50`
- `uv run uam install-hooks --client claude-code --target-dir . --profile focused`
- `uv run uam check-providers`

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

The server exposes `uam_search`, `uam_store`, `uam_get`, `uam_delete`, `uam_list`, `uam_sessions`, `uam_confirm_idea`, and `uam_dream`.

## Hook Installation

Template hook configs live under `hooks/`:

- `hooks/claude-code/settings.json`
- `hooks/codex/hooks.json`
- `hooks/copilot/hooks.json`
- `hooks/warp/uam-memory/SKILL.md`

The shared injector contract is:

- Claude Code and Codex `SessionStart` emit `{"system": "..."}`.
- Claude Code and Codex `UserPromptSubmit` emit `{"userPrompt": "..."}`.
- GitHub Copilot CLI `sessionStart` emits `{"additionalContext": "..."}`.
- GitHub Copilot CLI `userPromptSubmitted` is logged, but Copilot ignores stdout for that event.

Hook handlers are deterministic and model-free. They normalize payloads, enqueue events locally, trigger async processing, capture latency metrics, and always exit `0` so agent sessions are not blocked on local failures.

## Runtime profiles and offline processing

UAM now supports named runtime profiles backed by `uam-profiles.json`. A profile currently defines the memory prefix used for session-start injection, and the hook installer can bake a selected profile into generated hook commands.

Useful commands:

- `uv run uam profiles` — list the effective default profile and all known profiles
- `uv run uam save-profile focused --memory-prefix profiles/focused` — create or update a profile
- `uv run uam set-default-profile focused` — set the default profile used when hooks do not pass `--profile`
- `uv run uam install-hooks --client claude-code --target-dir . --profile focused` — install hooks pinned to a specific profile

Hook events are first written to a local SQLite state file at `state/uam.sqlite3`, then processed asynchronously into Postgres, AGE, and pgvector. This keeps hook latency low and preserves events when the active profile or database is unavailable.

Cached hook responses live in the same local state file. Session-start and user-prompt injections return cached content immediately when available, and queued event processing refreshes those cache entries afterward.

See [Installing in Claude Code](#installing-in-claude-code) and [Installing in GitHub Copilot CLI](#installing-in-github-copilot-cli) below for full instructions.

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

## Installing hooks with `uam install-hooks`

UAM ships a CLI command that reads the correct template for your harness, substitutes the UAM project root, and writes the hook configuration to the right place in any project directory.

```
uam install-hooks --client <harness> --target-dir <path/to/project> [--profile <profile-name>]
```

| `--client` | File written into `--target-dir` |
|---|---|
| `copilot` | `.github/hooks/uam-memory.json` |
| `claude-code` | `.claude/settings.json` |
| `codex` | `.codex/hooks.json` |

The command is idempotent: if the destination file already exists and its content is identical to what would be written, it prints "already up to date" and exits without touching the file. If the file exists with *different* content it prints a warning and exits non-zero so you can merge manually — this is intentional for `.claude/settings.json`, which often contains other per-project settings.

### Examples

```bash
# Install Copilot hooks into ~/projects/my-app
uv run uam install-hooks --client copilot --target-dir ~/projects/my-app

# Install Claude Code hooks using a named runtime profile
uv run uam install-hooks --client claude-code --target-dir . --profile focused

# Install Claude Code hooks into the current directory
uv run uam install-hooks --client claude-code --target-dir .

# Install Codex hooks on Windows
uv run uam install-hooks --client codex --target-dir "C:\Users\me\projects\my-app"
```

After running the command, restart the harness in the target project. The path inside the generated file always uses forward slashes so it works correctly on macOS and Linux; `uv` on Windows also accepts forward-slash paths.

---

## Installing in Claude Code

Claude Code fires hook events before and after every tool call, at session start and end, and on each user prompt. UAM captures all of these and uses `SessionStart` and `UserPromptSubmit` to inject relevant memories back into the session as context.

### Prerequisites

Complete the Setup steps at the top of this file first: Docker stack running, `uv sync --dev` done, `uv run uam migrate` applied. The handler always exits `0` so an unreachable database will not interrupt any session — events are queued locally either way, and cached injection content is returned when available.

### Where to install

Install hooks in `.claude/settings.json` at the root of whichever **other** project you want to observe — not in this repository. If hooks run here they capture UAM's own development activity. A typical workflow keeps UAM open in one Claude Code window with no hooks, and the observed project open in a second window with the hooks installed.

### Creating `.claude/settings.json`

Create `.claude/settings.json` in the observed project (or merge into it if it already exists). Replace `<UAM_PROJECT_DIR>` with the absolute path to this repository and **keep the surrounding double-quotes** — they prevent the shell from stripping backslashes on Windows:

```json
{
  "hooks": {
    "SessionStart": [
      {"hooks": [{"type": "command", "command": "uv run --directory \"<UAM_PROJECT_DIR>\" python -m uam.hooks.handler --client claude-code"}]}
    ],
    "UserPromptSubmit": [
      {"hooks": [{"type": "command", "command": "uv run --directory \"<UAM_PROJECT_DIR>\" python -m uam.hooks.handler --client claude-code"}]}
    ],
    "PreToolUse": [
      {"hooks": [{"type": "command", "command": "uv run --directory \"<UAM_PROJECT_DIR>\" python -m uam.hooks.handler --client claude-code"}]}
    ],
    "PostToolUse": [
      {"hooks": [{"type": "command", "command": "uv run --directory \"<UAM_PROJECT_DIR>\" python -m uam.hooks.handler --client claude-code"}]}
    ],
    "Stop": [
      {"hooks": [{"type": "command", "command": "uv run --directory \"<UAM_PROJECT_DIR>\" python -m uam.hooks.handler --client claude-code"}]}
    ],
    "SessionEnd": [
      {"hooks": [{"type": "command", "command": "uv run --directory \"<UAM_PROJECT_DIR>\" python -m uam.hooks.handler --client claude-code"}]}
    ]
  }
}
```

The expanded template with one hook object per block is in `hooks/claude-code/settings.json`.

### Restarting

Restart Claude Code in the observed project. Hooks take effect on the next session.

### Verifying

After opening a session in the observed project, confirm UAM is receiving and draining events:

```bash
# In UAM's directory:
uv run uam queue-status      # should show pending/done counts
uv run uam process-events    # optional manual drain if you do not want to wait for the background processor
uv run uam sessions          # should show the new session once processing completes
```

To confirm injection is working, watch stdout from the handler directly:

```bash
echo '{"hookEvent":"SessionStart","sessionId":"<real-uuid>","cwd":"/your/project"}' \
  | uv run python -m uam.hooks.handler --client claude-code
# should print {"system": "..."} once cached or stored profile memories exist
```

### What each event does

| Event | Queued / processed | Output to Claude Code |
|---|---|---|
| `SessionStart` | queued locally, then processed async | `{"system": "..."}` — profile memories injected into system prompt |
| `UserPromptSubmit` | queued locally, then processed async | `{"userPrompt": "..."}` — relevant memories prepended to user message |
| `PreToolUse` | queued locally, then processed async | none |
| `PostToolUse` | queued locally, then processed async | none |
| `Stop` | queued locally, then processed async | none |
| `SessionEnd` | queued locally, then processed async | none |

Injection (`SessionStart` and `UserPromptSubmit`) serves cached content immediately when available. Fresh cache entries are written from the live DB on a miss, and queued event processing refreshes them afterward.

## Installing in GitHub Copilot CLI

GitHub Copilot CLI can run repository hooks from `.github/hooks/*.json` in the observed project. UAM captures Copilot's hook events in the same event store as Claude Code, but Copilot's stdout contract is different: only `sessionStart` currently injects memory back into the session via `{"additionalContext": "..."}`. `userPromptSubmitted` is still logged, but Copilot ignores stdout for that event.

### Prerequisites

Complete the Setup steps at the top of this file first: Docker stack running, `uv sync --dev` done, `uv run uam migrate` applied.

On Windows, Copilot CLI hooks require PowerShell 7+ (`pwsh`) in `PATH`. Install it with `winget install Microsoft.PowerShell` if needed, then restart your terminal before starting Copilot CLI.

### Where to install

Install hooks in `.github/hooks/` at the root of whichever **other** project you want to observe — not in this repository. As with Claude Code, keeping UAM open in one window and the observed project open in another avoids logging UAM's own development activity.

### Creating `.github/hooks/uam-memory.json`

Create `.github/hooks/uam-memory.json` in the observed project. Replace `<UAM_PROJECT_DIR>` with the absolute path to this repository:

```json
{
  "version": 1,
  "hooks": {
    "sessionStart": [
      {
        "type": "command",
        "bash": "uv run python -m uam.hooks.handler --client copilot",
        "powershell": "uv run python -m uam.hooks.handler --client copilot",
        "cwd": "<UAM_PROJECT_DIR>",
        "timeoutSec": 30
      }
    ],
    "userPromptSubmitted": [
      {
        "type": "command",
        "bash": "uv run python -m uam.hooks.handler --client copilot",
        "powershell": "uv run python -m uam.hooks.handler --client copilot",
        "cwd": "<UAM_PROJECT_DIR>",
        "timeoutSec": 30
      }
    ],
    "preToolUse": [
      {
        "type": "command",
        "bash": "uv run python -m uam.hooks.handler --client copilot",
        "powershell": "uv run python -m uam.hooks.handler --client copilot",
        "cwd": "<UAM_PROJECT_DIR>",
        "timeoutSec": 30
      }
    ],
    "postToolUse": [
      {
        "type": "command",
        "bash": "uv run python -m uam.hooks.handler --client copilot",
        "powershell": "uv run python -m uam.hooks.handler --client copilot",
        "cwd": "<UAM_PROJECT_DIR>",
        "timeoutSec": 30
      }
    ],
    "agentStop": [
      {
        "type": "command",
        "bash": "uv run python -m uam.hooks.handler --client copilot",
        "powershell": "uv run python -m uam.hooks.handler --client copilot",
        "cwd": "<UAM_PROJECT_DIR>",
        "timeoutSec": 30
      }
    ],
    "sessionEnd": [
      {
        "type": "command",
        "bash": "uv run python -m uam.hooks.handler --client copilot",
        "powershell": "uv run python -m uam.hooks.handler --client copilot",
        "cwd": "<UAM_PROJECT_DIR>",
        "timeoutSec": 30
      }
    ]
  }
}
```

The matching template lives at `hooks/copilot/hooks.json`. Append `--profile <name>` to each command if you want Copilot hooks pinned to a named runtime profile instead of the current default.

### Restarting

Restart Copilot CLI in the observed project. Hook configuration is loaded when the CLI starts, so an already-running session will not see new hooks until it is restarted.

### Verifying

After opening a new Copilot CLI session in the observed project, confirm UAM is receiving and draining events:

```powershell
uv run uam queue-status
uv run uam process-events
uv run uam sessions
```

To test the handler directly:

```powershell
'{"hook_event_name":"sessionStart","sessionId":"<real-uuid>","timestamp":1716400000123,"cwd":"C:\\your\\project"}' | uv run python -m uam.hooks.handler --client copilot
# should print {"additionalContext": "..."} once cached or stored profile memories exist
```

### What each event does

| Event | Queued / processed | Output to Copilot CLI |
|---|---|---|
| `sessionStart` | queued locally, then processed async | `{"additionalContext": "..."}` — profile memories injected into the session |
| `userPromptSubmitted` | queued locally, then processed async | none — Copilot ignores stdout for this event |
| `preToolUse` | queued locally, then processed async | none |
| `postToolUse` | queued locally, then processed async | none |
| `agentStop` | queued locally, then processed async | none |
| `sessionEnd` | queued locally, then processed async | none |

As with Claude Code, database failures never block the session: the handler queues locally, serves cached context when it can, and exits `0`.

## Local smoke sequence

For a quick manual smoke pass on a clean machine:

Prerequisites: Docker Desktop, `uv`, Node.js, and Ollama with `nomic-embed-text` and `mistral` pulled (`ollama pull nomic-embed-text && ollama pull mistral`).

1. Start Docker Desktop.
2. `cd db_stack && cp .env.example .env`
3. `docker build -t pguam:18.4 -f Dockerfile_pguam18.4 .`
4. `docker compose up -d db`
5. `cd .. && uv sync --dev`
6. `uv run uam migrate`
7. `uv run uam save-profile focused --memory-prefix profiles/focused`
8. Pipe a sample hook payload and confirm injection output:
   ```bash
   echo '{"hookEvent":"SessionStart","sessionId":"00000000-0000-7000-8000-000000000001","cwd":"/your/project"}' \
     | uv run python -m uam.hooks.handler --client claude-code --profile focused
   # expect: {"system": "..."}
   ```
9. `uv run uam queue-status`
10. `uv run uam process-events`
11. `uv run uam search "sample"`
12. `uv run uam dream --dry-run`
