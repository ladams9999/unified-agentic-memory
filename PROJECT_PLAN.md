# Project plan for unified-agentic-memory

Build a single, shared memory layer for work across multiple coding agents: Claude Code, Github Copilot, Codex, and Warp.

## Completed Goals

### Goal 1 — Cross-platform harness integration ✓

- Hook config templates for GitHub Copilot, Claude Code, Codex, and Warp audited and corrected for all platforms (Windows, macOS, Linux).
- `uam install-hooks --client <harness> --target-dir <path>` CLI command added: reads the template, substitutes the UAM project path, and writes the hook file to the correct location in the target project. Idempotent.
- `cwd` field in incoming hook payloads normalized to forward slashes on all platforms (Windows backslash paths stored consistently).
- README updated with a platform support matrix and macOS/Linux prerequisites.

### Goal 2 — Remote model support ✓

- OpenAI and OpenRouter added as configurable providers for both embeddings and LLM generation alongside the existing Ollama provider.
- Provider selected via `UAM_EMBEDDING_PROVIDER` (`ollama` | `openai`) and `UAM_LLM_PROVIDER` (`ollama` | `openai` | `openrouter`).
- OpenAI embedding requests pin `dimensions=768` to match the existing pgvector schema — no migration required.
- `uam check-providers` CLI command added to validate connectivity for the configured providers.
- All factory calls raise `ValueError` on unrecognised provider names (no silent fallback).

### Goal 3 — Remote Postgres / Supabase support ✓

- SSL connection string support: `UAM_DB_SSLMODE` setting (default `prefer`; set to `require` for Supabase or remote TLS).
- Apache AGE made optional: `UAM_DISABLE_GRAPH=true` disables graph projection; all other features (events, memories, search, dream, session timeline, MCP) continue to work.
- AGE DDL extracted from the base migration into `db_stack/migrations/0002_age_graph.sql`; the migration runner automatically skips it when AGE is not installed, printing a warning to stderr.
- Supabase setup documented in README.

## Current Goals

### Goal 4

Prerequisites: Goals 2 and 3 (both complete).

- Verify UAM works end-to-end on a lightweight machine using a fully remote setup (remote Postgres + remote model provider).
- Verify UAM works with multiple harnesses running simultaneously against the same database.
- Verify UAM works across multiple machines simultaneously.


## Memory Structure

### Basic Memory

Data will come from the coding agent, the data stored as markdown in the database.  Data from hooks will be stored as task diaries in the knowledge graph, and will be periodically reviewed by an agent to extract observations and conclusions which will also be placed in the knowledge graph.  Additionally an agent will review the recent entries (7ish days) in the knowledge graph and append key learnings.

For each markdown entity:

- Content and metadata will stored in relational db
- Content will be embedded into a vector db
- Content will be added to a graph database to maintain relationships and hierarchy
- Content will be indexed for full text search
- Synthesized data will be versioned as learnings and conclusions change.  Facts will be static.  

Recent learnings will be collected and cached and provided back to agent.

## Setup for development

- Postgres with pgvector for vector storage
- Postgres relational tables as source-of-truth event storage
- Postgres with Apache AGE for graph projection and traversal
- Ollama using `nomic-embed-text` for embeddings
- Ollama using `phi4-mini`, `phi4-mini-reasoning`, or `mistral` (Mistral 7B) for prose work
- Python
- uv to manage project
- pg_cron installed and available (scheduling policy deferred)

## Hooks

- SessionStart: Fires before agent reads system prompt, anything emitted gets prepended to the system prompt
- UserPromptSubmit: Fires just before the user message, and anything emitted gets appended to user prompt 
- PreToolUse: 
- PostToolUse:
- Stop:
- SessionEnd: Or similar hooks where supported (onSessionEnd in Github Copilot would become this) to start dreaming

Each hook will receive a JSON payload on stdin, which should include:
- Session ID
- Agent name
- Model name
- Event name
- Tool details
- User prompt

Each hook can also emit JSON on stdout to inject additional context back into the conversation.

Hooks should be deterministic and model-free. Initial latency targets are measurement-first: capture local timing metrics (p50/p95) and set strict budgets after observing real runs.

There will need to be skill sets for Claude Code, Codex, Github Copilot, and Warp.

Warp v1 integration is skill + CLI only.

## Shared memory layer

UUID7 for event ID

### Relational event store (source of truth)

All incoming hook events are stored in an append-only relational table with:

- Raw payload JSONB (lossless copy of input)
- Normalized query fields (session ID, client, agent/model, event name, tool details, prompt, cwd, timestamps)
- Payload schema version for forward migrations

This preserves all delivered information for future schema evolution and replay.

### Graph db

In the graph database, each agent session is a node, connected to a linked list of event nodes (one per hook invocation). Events are typed by the event that triggered them (SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, and Stop).

The graph is projected from relational events and can be rebuilt from the append-only event table if schema or graph shape changes.

### Vector db

#### Vector Indexing

- Read the content of the memory
- Event ID for document ID
- Send the first 2,000 characters to Ollama's embedding endpoint
- Store the embedding, the memory, and metadata (category, title, path) in the vector store.

Re-running the indexer updates memories that already have an ID in the collection.

### Full text search

Each relational event and memory will be indexed for full text search.

## Action Review

A periodic job that reviews recent sessions and events then summarizes what happened, adding to memory state and updating responses to agents.  Will probably run after session end depending on performance.

## Dream Phase

A periodic batch job that extracts from sessions, summarizes what happened, and updates memory state. pg_cron is available; specific cadence is deferred for v1 and can be run manually, from session end hooks, or scheduled later.

The batch job pulls every event since last run, and hands them to the model with the current memory store, and is asked to write back a small set of durable notes, imitating a markdown wiki.  Each memory is a file at a semantic path, with YAML frontmatter on top and regular text below.  The model will merge rather than append, and if something new contradicts an old note, the old note gets rewritten.

## Memory Access

Besides receiving data from the hooks, a model can search for relevant memories, store new info, and update or remove existing entries via MCP tools.

## Summary

- Hooks passively log every event to relational source-of-truth storage, without model calls.
- Graph views are projected from relational events for traversal and relationship queries.
- Dream Phase and Action Review read accumulated events, distilling them into durable markdown memories.  Memories are organized by topic, and merged rather than appended.
- Injection on session start from any harness, profile memories are loaded into context. On user prompt, relevant memories are searched and appended automatically

## Search

Searches can be limited to events, memories, or both.  Standard search fetches from vector store, full text search, and memory store, and the results are combined, reranked, and then truncated before presenting to a model or user.

Searches will be cached until the next dream phase.  Some searches will then be precached.

## Usage

Besides the CLI and MCP, there will be an api and simple web interface.  The web interface will have a search with all options, a browser for sessions and memories, and show stats and some log data. 

In v1, Warp uses skill + CLI instead of MCP.

### pguam18.4

A docker based postgres db is defined in `db_stack` 

## Testing

Use pytest for unit testing
