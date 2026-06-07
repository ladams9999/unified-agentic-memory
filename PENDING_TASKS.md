# Pending Tasks for unified-agentic-memory

---

## Active implementation: setup profiles and offline event storage

- [ ] **SP2** — Add a durable local event queue so hook handlers append normalized events before any heavier processing and preserve events when profile/database work fails.
- [ ] **SP3** — Split hook ingestion into capture and asynchronous processing, including replay/flush commands and retry-safe queued processing through the existing relational ingest path.
- [ ] **SP4** — Add cached hook responses that can be served immediately and refreshed after queued events are processed.
- [ ] **SP5** — Add tests and documentation updates for profiles, offline queueing, async processing, cached responses, and any resulting README / IMPLEMENTATION / PROJECT_PLAN changes.

---

## Deferred by design (v1 scope)

- **pg_cron scheduling policy** — `pg_cron` is installed and smoke-tested. Specific schedule cadence for the dream phase is intentionally deferred until real usage data is available.
- **Security hardening** — API has no authentication. Local single-user assumptions hold for v1. Add hardening before any remote or multi-user deployment.
- **Warp MCP integration** — Warp v1 uses skill + CLI only. MCP integration deferred.
- **Search/index tuning** — Cache TTL and RRF weights use default values. Tuning deferred until real data volume exists.
