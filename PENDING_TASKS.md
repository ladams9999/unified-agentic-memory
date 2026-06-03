# Pending Tasks for unified-agentic-memory

---

## Goal 1: Cross-Platform Harness Integration

- [ ] **G1-CP-3** Add `uam install-hooks` CLI command to `src/uam/cli.py` with `--client` (copilot/claude-code/codex) and `--target-dir` options; reads template, substitutes `<UAM_PROJECT_DIR>`, writes to correct location in target dir.
- [ ] **G1-CP-4** Update `README.md`: add platform support matrix table, macOS/Linux prerequisites for `uv`, and `uam install-hooks` usage examples for each client.

---

## Deferred by design (v1 scope)

- **pg_cron scheduling policy** — `pg_cron` is installed and smoke-tested. Specific schedule cadence for the dream phase is intentionally deferred until real usage data is available.
- **Security hardening** — API has no authentication. Local single-user assumptions hold for v1. Add hardening before any remote or multi-user deployment.
- **Warp MCP integration** — Warp v1 uses skill + CLI only. MCP integration deferred.
- **Search/index tuning** — Cache TTL and RRF weights use default values. Tuning deferred until real data volume exists.
