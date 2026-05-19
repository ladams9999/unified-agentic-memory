# Project plan for unified-agentic-memory

Build a single, shared memory layer for work across multiple coding agents: Claude Code, Github Copilot, Codex, and Warp.

## Setup

- Postgres with pgvector for vector storage
- Postgres with Apache AGE for graph storage
- Ollama using `nomic-embed-text` for embeddings
- Ollama using `Mistral 7B`, `Phi-4`, or `SmolLM3` (TBD) for prose work
- Python
- uv to manage project
- 

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

There will need to skill sets for Claude Code, Codex, Github Copilot, and Warp

## Shared memory layer

UUID7 for event ID

### Graph db

In the graph database, each agent session is a node, connected to a linked list of event nodes (one per hook invocation). Events are typed by the event that triggered them (SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, and Stop).

### Vector db

#### Vector Indexing

- Read the content of the memory
- Event ID for document ID
- Send the first 2,000 characters to Ollama's embedding endpoint
- Store the embedding, the memory, and metadata (category, title, path) in the vector store.

Re-running the indexer updates memories that already have an ID in the collection.

### Full text search

Each event and memory will be indexed for full text search

## Dream Phase

A periodic batch job that extracts facts from sessions, summarizes what happened, and updates the graph.  It should run every few hours, or after session end where supported, reading the events accumulated since last run, and writes back to the memory store.

The batch job pulls every event since last run, and hands them to the model with the current memory store, and is asked to write back a small set of durable notes, imitating a markdown wiki.  Each memory is a file at a semantic path, with YAML frontmatter on top and regular text below.  The model will merge rather than append, and if something new contradicts an old note, the old note gets rewritten.

## Memory Access

Besides receiving data from the hooks, a model can search for relevant memories, store new info, and update or remove existing entries via MCP tools.

## Summary

- Hooks passively log every event into graph storage, without model calls.
- Dream Phase reads accumulated events, distilling them into durable markdown memories.  Memories are organized by topic, and merged rather than appended.
- Injection on session start from any harness, profile memories are loaded into context. On user prompt, relevant memories are searched and appended automatically

## Search

Searches can be limited to events, memories, or both.  Standard search fetches from vector store, full text search, and memory store, and the results are combined, reranked, and then truncated before presenting to a model or user.

Searches will be cached until the next dream phase.  Some searches will then be precached.

## Usage

Besides the CLI and MCP, there will be an api and simple web interface.  The web interface will have a search with all options, a browser for sessions and memories, and show stats and some log data. 

### pguam18.4

A docker based postgres db is defined in `db_stack` 

## Testing

Use pytest for unit testing
