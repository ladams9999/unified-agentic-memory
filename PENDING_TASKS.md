# Pending Tasks for unified-agentic-memory

All runtime validation tasks have been completed. The items below are deferred by design or out of scope for v1.

---

## Deferred by design (v1 scope)

- **pg_cron scheduling policy** — `pg_cron` is installed and smoke-tested. Specific schedule cadence for the dream phase is intentionally deferred until real usage data is available.
- **Security hardening** — API has no authentication. Local single-user assumptions hold for v1. Add hardening before any remote or multi-user deployment.
- **Warp MCP integration** — Warp v1 uses skill + CLI only. MCP integration deferred.
- **NEXT_EVENT / Memory / REMEMBERS AGE labels** — `Memory` vertex and `REMEMBERS` edge are described in IMPLEMENTATION.md but not yet implemented in graph code. `NEXT_EVENT` is lazily created on ingest. Full graph relationship model is future work.
- **Search/index tuning** — Cache TTL and RRF weights use default values. Tuning deferred until real data volume exists.
