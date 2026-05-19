# Implementation Review

## Scope for this review

This review reflects the agreed first version scope:

- Personal tool running on a laptop with local resources.
- Warp integration is CLI-skill only for v1.
- Event data should be stored relationally as source of truth.
- pg_cron should be installed and available, with scheduling decisions deferred.
- Security is important but hardening for remote or multi-user use is deferred until needed.

## Summary

The current plan is strong and practical for local-first delivery. The most important improvement is to make relational event storage explicit and lossless, then treat AGE as a projection and traversal layer. This preserves migration flexibility while keeping graph capabilities.

## Updated findings

1. Relational-first events should be explicit in design and tasks.
   - Persist full raw hook payloads in JSONB plus normalized columns.
   - Keep rows append-only for reliable future migration.

2. Migration scaffolding should be added early.
   - Even for local use, versioned schema migration avoids rework and data drift.

3. Hook latency should be measurement-first.
   - Add instrumentation and gather p50/p95 before setting strict budgets.

4. pg_cron should be verified but not overcommitted.
   - Install and smoke-test extension now.
   - Defer production schedule policy until behavior is better understood.

5. Warp should remain CLI-skill only in v1.
   - Keep this as the single path for Warp to reduce moving parts.

6. Security should be staged.
   - Keep local assumptions in v1.
   - Add hardening once remote services or multi-user access are introduced.

## Recommended plan changes

1. Add an explicit event table model under database schema.
2. Add migration baseline tasks.
3. Add event projection from relational rows to AGE graph.
4. Add hook timing metrics and reporting.
5. Update wording so Warp is not described as MCP-enabled in v1.
6. Clarify that pg_cron is available in v1 and scheduling is optional.

## Revised risk priority

1. High: No explicit lossless event schema and migration baseline.
2. Medium: Unknown hook latency until instrumented.
3. Medium: Search/index tuning deferred until real data volume exists.
4. Low in v1: Security hardening beyond local single-user boundaries.

## Acceptance signal for this revision

This revision is complete when:

- Implementation plan states relational-first source of truth for events.
- Pending tasks include events table, migration baseline, projection, and latency instrumentation.
- Warp is CLI-skill only in v1 docs.
- pg_cron is listed as available and smoke-tested, with scheduling deferred.