# Pending Tasks for unified-agentic-memory

---

## Goal 3: Remote Postgres / Supabase Support

- [ ] **G3-1** — Add `db_sslmode` and `disable_graph` fields to `Settings` in `src/uam/config.py`; append `sslmode=` to both `database_url` and `postgres_database_url`; update `db_stack/.env.example` with new vars and comments.
- [ ] **G3-2** — Add `is_age_available(conn) -> bool` and `try_ensure_age(conn) -> bool` to `src/uam/db.py`; keep existing `ensure_age()` unchanged.
- [ ] **G3-3** — Guard all public AGE-writing functions in `src/uam/projection.py` with `if settings.disable_graph: return` (matching return types).
- [ ] **G3-4** — Extract AGE-specific DDL from `db_stack/migrations/0001_initial_schema.sql` into new `db_stack/migrations/0003_age_graph.sql`; update `apply_migrations()` in `src/uam/db.py` to skip `*_age.sql` files when AGE is unavailable.
- [ ] **G3-5** — Add tests for disabled-graph mode in `tests/test_graph_disabled.py`: guard short-circuits, `is_age_available()` with fake connections, AGE migration skip logic.
- [ ] **G3-6** — Add "## Using Supabase" section to `README.md` documenting pgvector setup, required env vars, `uam migrate` behavior, and feature limitations.

## Deferred by design (v1 scope)

- **pg_cron scheduling policy** — `pg_cron` is installed and smoke-tested. Specific schedule cadence for the dream phase is intentionally deferred until real usage data is available.
- **Security hardening** — API has no authentication. Local single-user assumptions hold for v1. Add hardening before any remote or multi-user deployment.
- **Warp MCP integration** — Warp v1 uses skill + CLI only. MCP integration deferred.
- **Search/index tuning** — Cache TTL and RRF weights use default values. Tuning deferred until real data volume exists.
