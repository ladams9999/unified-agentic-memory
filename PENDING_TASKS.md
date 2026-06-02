# Pending Tasks for unified-agentic-memory

---

## Element 2: Memory types — fact / learning / idea + idea promotion

- [ ] **T1** — Write `db_stack/migrations/0002_memory_type.sql`: add `memory_type TEXT NOT NULL DEFAULT 'learning' CHECK (memory_type IN ('fact', 'learning', 'idea'))` to `uam.memories`.
- [ ] **T2** — Add `MemoryType` enum (`fact`, `learning`, `idea`) to `src/uam/models.py` and add `memory_type: MemoryType = MemoryType.learning` field to `Memory`.
- [ ] **T3** — Update all SQL queries in `src/uam/memories.py` to include `memory_type` in SELECT and INSERT/UPDATE. Update `_memory_from_row()` to read column index 7. `upsert_memory()` accepts optional `memory_type` parameter (default `learning`).
- [ ] **T4** — In `upsert_memory()`, raise `ValueError` if an existing record has `memory_type='fact'` (facts cannot be overwritten).
- [ ] **T5** — Add `confirm_idea(path, conn=None)` to `src/uam/memories.py` that promotes `memory_type` from `idea` → `learning`. Raises `ValueError` if the memory does not exist or is not an `idea`.
- [ ] **T6** — In `src/uam/mcp_server.py`, expose `uam_confirm_idea(path)` tool. Guard `uam_store` to reject writes where the stored memory is a `fact`.
- [ ] **T7** — Update dream prompt in `src/uam/dream.py` to instruct the model to include `type: fact | learning | idea` in each memory's YAML frontmatter. Parse this field in `parse_memory_blocks()` and pass it to `upsert_memory()`.
- [ ] **T8** — Add `confirm-idea <path>` subcommand to `src/uam/cli.py`. Display `memory_type` in `list` and `get` output.

---

## Deferred by design (v1 scope)

- **pg_cron scheduling policy** — `pg_cron` is installed and smoke-tested. Specific schedule cadence for the dream phase is intentionally deferred until real usage data is available.
- **Security hardening** — API has no authentication. Local single-user assumptions hold for v1. Add hardening before any remote or multi-user deployment.
- **Warp MCP integration** — Warp v1 uses skill + CLI only. MCP integration deferred.
- **Search/index tuning** — Cache TTL and RRF weights use default values. Tuning deferred until real data volume exists.
