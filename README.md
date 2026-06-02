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
- `uv run uam dream`

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

- Claude Code and Codex `SessionStart` emit `{"system": "..."}`.
- Claude Code and Codex `UserPromptSubmit` emit `{"userPrompt": "..."}`.
- GitHub Copilot CLI `sessionStart` emits `{"additionalContext": "..."}`.
- GitHub Copilot CLI `userPromptSubmitted` is logged, but Copilot ignores stdout for that event.

Hook handlers are deterministic and model-free. They normalize payloads, log events, capture latency metrics, and always exit `0` so agent sessions are not blocked on local failures.

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

## Installing in Claude Code

Claude Code fires hook events before and after every tool call, at session start and end, and on each user prompt. UAM captures all of these and uses `SessionStart` and `UserPromptSubmit` to inject relevant memories back into the session as context.

### Prerequisites

Complete the Setup steps at the top of this file first: Docker stack running, `uv sync --dev` done, `uv run uam migrate` applied. The handler always exits `0` so an unreachable database will not interrupt any session — but nothing is stored or injected until the database is reachable.

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

After opening a session in the observed project, confirm UAM is receiving events:

```bash
# In UAM's directory:
uv run uam sessions          # should show the new session
tail -f logs/hook-handler.log  # live event stream
```

To confirm injection is working, watch stdout from the handler directly:

```bash
echo '{"hookEvent":"SessionStart","sessionId":"<real-uuid>","cwd":"/your/project"}' \
  | uv run python -m uam.hooks.handler --client claude-code
# should print {"system": "..."} once there are profile memories stored
```

### What each event does

| Event | Stored in DB | Output to Claude Code |
|---|---|---|
| `SessionStart` | yes | `{"system": "..."}` — profile memories injected into system prompt |
| `UserPromptSubmit` | yes | `{"userPrompt": "..."}` — relevant memories prepended to user message |
| `PreToolUse` | yes | none |
| `PostToolUse` | yes | none |
| `Stop` | yes | none |
| `SessionEnd` | yes | none |

Injection (`SessionStart` and `UserPromptSubmit`) only runs when the database is reachable. If it fails the event is still logged locally and the handler exits `0`.

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

The matching template lives at `hooks/copilot/hooks.json`.

### Restarting

Restart Copilot CLI in the observed project. Hook configuration is loaded when the CLI starts, so an already-running session will not see new hooks until it is restarted.

### Verifying

After opening a new Copilot CLI session in the observed project, confirm UAM is receiving events:

```powershell
uv run uam sessions
Get-Content logs\hook-handler.log -Wait
```

To test the handler directly:

```powershell
'{"hook_event_name":"sessionStart","sessionId":"<real-uuid>","timestamp":1716400000123,"cwd":"C:\\your\\project"}' | uv run python -m uam.hooks.handler --client copilot
# should print {"additionalContext": "..."} once there are profile memories stored
```

### What each event does

| Event | Stored in DB | Output to Copilot CLI |
|---|---|---|
| `sessionStart` | yes | `{"additionalContext": "..."}` — profile memories injected into the session |
| `userPromptSubmitted` | yes | none — Copilot ignores stdout for this event |
| `preToolUse` | yes | none |
| `postToolUse` | yes | none |
| `agentStop` | yes | none |
| `sessionEnd` | yes | none |

As with Claude Code, database failures never block the session: the handler logs locally and exits `0`.

## Local smoke sequence

For a quick manual smoke pass on a clean machine:

Prerequisites: Docker Desktop, `uv`, Node.js, and Ollama with `nomic-embed-text` and `mistral` pulled (`ollama pull nomic-embed-text && ollama pull mistral`).

1. Start Docker Desktop.
2. `cd db_stack && cp .env.example .env`
3. `docker build -t pguam:18.4 -f Dockerfile_pguam18.4 .`
4. `docker compose up -d db`
5. `cd .. && uv sync --dev`
6. `uv run uam migrate`
7. Pipe a sample hook payload and confirm injection output:
   ```bash
   echo '{"hookEvent":"SessionStart","sessionId":"00000000-0000-7000-8000-000000000001","cwd":"/your/project"}' \
     | uv run python -m uam.hooks.handler --client claude-code
   # expect: {"system": "..."}
   ```
8. `uv run uam search "sample"`
9. `uv run uam dream --dry-run`
