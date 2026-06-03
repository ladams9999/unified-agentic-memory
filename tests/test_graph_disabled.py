"""Tests for disabled-graph mode (settings.disable_graph = True) and AGE availability checks."""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

import uam.projection as projection_mod
from uam.db import _is_age_migration, apply_migrations, is_age_available


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeAgeConn:
    """Minimal fake connection for is_age_available tests."""

    def __init__(self, age_count: int) -> None:
        self._age_count = age_count

    def execute(self, query: str, params: Any = None) -> "_FakeResult":
        if "pg_extension" in query and "extname = 'age'" in query:
            return _FakeResult([(self._age_count,)])
        raise AssertionError(f"Unexpected query: {query!r}")


class _FakeResult:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def fetchone(self) -> Any:
        return self._rows[0] if self._rows else None

    def fetchall(self) -> list[Any]:
        return list(self._rows)


# ---------------------------------------------------------------------------
# is_age_available
# ---------------------------------------------------------------------------


def test_is_age_available_returns_false_when_extension_absent():
    conn = _FakeAgeConn(age_count=0)
    assert is_age_available(conn) is False


def test_is_age_available_returns_true_when_extension_present():
    conn = _FakeAgeConn(age_count=1)
    assert is_age_available(conn) is True


# ---------------------------------------------------------------------------
# projection guards
# ---------------------------------------------------------------------------


def test_project_event_skips_cypher_when_disabled(monkeypatch):
    """project_event must return without calling any Cypher helper when disable_graph=True."""
    monkeypatch.setattr(projection_mod.settings, "disable_graph", True)

    def _fail_cypher(*args, **kwargs):
        raise AssertionError("Cypher should not be called when disable_graph=True")

    # Patch every graph helper that project_event could call
    monkeypatch.setattr(projection_mod, "create_session", _fail_cypher)
    monkeypatch.setattr(projection_mod, "create_event", _fail_cypher)
    monkeypatch.setattr(projection_mod, "link_event", _fail_cypher)

    fake_conn = MagicMock()
    # project_event must return None without calling anything
    result = projection_mod.project_event(
        fake_conn,
        {
            "id": uuid.uuid4(),
            "session_id": uuid.uuid4(),
            "client": "claude-code",
            "event_name": "SessionStart",
            "occurred_at": "2026-01-01T00:00:00+00:00",
        },
    )
    assert result is None
    fake_conn.execute.assert_not_called()


def test_project_memory_skips_cypher_when_disabled(monkeypatch):
    monkeypatch.setattr(projection_mod.settings, "disable_graph", True)

    def _fail_upsert(*args, **kwargs):
        raise AssertionError("upsert_memory_node should not be called when disable_graph=True")

    monkeypatch.setattr(projection_mod, "upsert_memory_node", _fail_upsert)

    from uam.models import Memory

    mem = Memory(id=uuid.uuid4(), path="foo/bar", frontmatter={}, content="hello")
    result = projection_mod.project_memory(object(), mem)
    assert result is None


def test_remove_memory_projection_skips_cypher_when_disabled(monkeypatch):
    monkeypatch.setattr(projection_mod.settings, "disable_graph", True)

    def _fail_delete(*args, **kwargs):
        raise AssertionError("delete_memory_node should not be called when disable_graph=True")

    monkeypatch.setattr(projection_mod, "delete_memory_node", _fail_delete)

    result = projection_mod.remove_memory_projection(object(), "foo/bar")
    assert result is None


def test_replay_relational_memories_returns_zero_when_disabled(monkeypatch):
    monkeypatch.setattr(projection_mod.settings, "disable_graph", True)
    fake_conn = MagicMock()
    result = projection_mod.replay_relational_memories(fake_conn)
    assert result == 0
    fake_conn.execute.assert_not_called()


def test_replay_relational_events_returns_zero_when_disabled(monkeypatch):
    monkeypatch.setattr(projection_mod.settings, "disable_graph", True)
    fake_conn = MagicMock()
    result = projection_mod.replay_relational_events(fake_conn)
    assert result == 0
    fake_conn.execute.assert_not_called()


# ---------------------------------------------------------------------------
# apply_migrations skips AGE files when AGE is unavailable
# ---------------------------------------------------------------------------


class _FakeMigrationConn:
    """Minimal fake connection for apply_migrations tests."""

    def __init__(self, age_available: bool) -> None:
        self._age_available = age_available
        self.executed: list[str] = []
        self._applied: set[str] = set()

    def execute(self, query: str, params: Any = None) -> "_FakeResult":
        self.executed.append(query.strip()[:80])
        # schema_migrations DDL
        if "CREATE SCHEMA" in query or "CREATE TABLE IF NOT EXISTS uam.schema_migrations" in query:
            return _FakeResult([])
        # SELECT applied migrations
        if "SELECT filename FROM uam.schema_migrations" in query:
            return _FakeResult([(f,) for f in sorted(self._applied)])
        # pg_extension check (is_age_available)
        if "pg_extension" in query and "extname = 'age'" in query:
            return _FakeResult([(1 if self._age_available else 0,)])
        # INSERT applied migration
        if "INSERT INTO uam.schema_migrations" in query and params:
            self._applied.add(params[0])
            return _FakeResult([])
        # Any other SQL (migration body) — just record it
        return _FakeResult([])


def test_apply_migrations_skips_age_file_when_age_unavailable(tmp_path: Path):
    """AGE migration file must be skipped (not executed, not recorded) when AGE is absent."""
    # Write a normal migration and an AGE migration
    (tmp_path / "0001_base.sql").write_text("SELECT 1;", encoding="utf-8")
    (tmp_path / "0003_age_graph.sql").write_text("LOAD 'age';", encoding="utf-8")

    conn = _FakeMigrationConn(age_available=False)
    applied = apply_migrations(conn, directory=tmp_path)

    assert "0001_base.sql" in applied
    assert "0003_age_graph.sql" not in applied
    # The AGE SQL body must not appear in executed statements
    assert not any("LOAD 'age'" in s for s in conn.executed)


def test_apply_migrations_applies_age_file_when_age_available(tmp_path: Path):
    """AGE migration file must be applied when AGE is present."""
    (tmp_path / "0001_base.sql").write_text("SELECT 1;", encoding="utf-8")
    (tmp_path / "0003_age_graph.sql").write_text("LOAD 'age';", encoding="utf-8")

    conn = _FakeMigrationConn(age_available=True)
    applied = apply_migrations(conn, directory=tmp_path)

    assert "0001_base.sql" in applied
    assert "0003_age_graph.sql" in applied


def test_apply_migrations_skips_custom_age_sql_file(tmp_path: Path):
    """Any file ending in _age.sql should be skipped when AGE is absent."""
    (tmp_path / "0010_custom_age.sql").write_text("SELECT 'age stuff';", encoding="utf-8")

    conn = _FakeMigrationConn(age_available=False)
    applied = apply_migrations(conn, directory=tmp_path)

    assert "0010_custom_age.sql" not in applied


# ---------------------------------------------------------------------------
# _is_age_migration helper
# ---------------------------------------------------------------------------


def test_is_age_migration_identifies_canonical_file():
    assert _is_age_migration("0003_age_graph.sql") is True


def test_is_age_migration_identifies_suffix_pattern():
    assert _is_age_migration("0010_custom_age.sql") is True


def test_is_age_migration_returns_false_for_regular_files():
    assert _is_age_migration("0001_initial_schema.sql") is False
    assert _is_age_migration("0002_memory_type.sql") is False
