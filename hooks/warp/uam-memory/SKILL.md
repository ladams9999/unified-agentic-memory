---
name: uam-memory
description: Use the local uam CLI to search, store, retrieve, and summarize unified agent memory.
---

Use the following commands for memory operations:

- `uv run uam search "<query>" --scope all --limit 5`
- `uv run uam store "<path>" "<content>" --frontmatter '{"title":"..."}'`
- `uv run uam get "<path>"`
- `uv run uam delete "<path>"`
- `uv run uam list "<prefix>"`
- `uv run uam sessions`
- `uv run uam dream --dry-run`
