from __future__ import annotations

from datetime import datetime, timezone

from uam import dream


class FakeDreamConnection:
    def __init__(self) -> None:
        self.cache_truncated = False
        self.inserted = []

    def execute(self, query, params=None):
        class Result:
            def __init__(self, rows=None, row=None):
                self._rows = rows or []
                self._row = row

            def fetchone(self):
                return self._row

            def fetchall(self):
                return self._rows

        if "SELECT MAX(watermark)" in query:
            return Result(row=(None,))
        if "FROM uam.events" in query:
            return Result(
                rows=[
                    ("event-1", "UserPromptSubmit", datetime(2026, 1, 1, tzinfo=timezone.utc), "search postgres"),
                ]
            )
        if "INSERT INTO uam.dream_runs" in query:
            self.inserted.append(params)
            return Result()
        if "TRUNCATE uam.search_cache" in query:
            self.cache_truncated = True
            return Result()
        raise AssertionError(query)

    def commit(self):
        return None


class FakeLLM:
    def generate(self, prompt: str, system: str) -> str:
        assert "Recent events" in prompt
        return """```memory topics/postgres.md
---
title: Postgres setup
---
Use pgvector and AGE.
```"""


def test_run_dream_upserts_memories(monkeypatch):
    conn = FakeDreamConnection()
    stored = []

    monkeypatch.setattr(dream, "list_memories", lambda conn=None: [])
    monkeypatch.setattr(
        dream,
        "upsert_memory",
        lambda path, frontmatter, content, conn=None, embedder=None: stored.append((path, frontmatter, content)),
    )

    result = dream.run_dream(conn=conn, llm=FakeLLM())
    assert result.events_processed == 1
    assert result.memories_updated == 1
    assert stored[0][0] == "topics/postgres.md"
    assert conn.cache_truncated is True
