from __future__ import annotations

from datetime import datetime, timezone

from uam.models import SearchResult
from uam import search


class StubEmbedder:
    def embed(self, text: str) -> list[float]:
        return [1.0] * 768


class FakeSearchConnection:
    def __init__(self) -> None:
        self.cached = None
        self.pruned = False

    def execute(self, query, params=None):
        class Result:
            def __init__(self, rows=None, row=None):
                self._rows = rows or []
                self._row = row

            def fetchone(self):
                return self._row

            def fetchall(self):
                return self._rows

        if "SELECT results" in query:
            return Result(row=(self.cached,) if self.cached is not None else None)
        if "DELETE FROM uam.search_cache" in query:
            self.pruned = True
            return Result()
        if "INSERT INTO uam.search_cache" in query:
            self.cached = params[1]
            return Result()
        if "FROM uam.events" in query:
            return Result(
                rows=[
                    ("event-1", "SessionStart", "session content", 0.7),
                    ("event-2", "UserPromptSubmit", "prompt content", 0.5),
                ]
            )
        if "FROM uam.memories" in query:
            return Result(rows=[("memory-1", "topics/a.md", "memory content", 0.9)])
        raise AssertionError(query)

    def commit(self):
        return None


def test_rrf_changes_rank():
    vector_only = [
        SearchResult(id="1", source="memory", title="A", content="A", score=1.0),
        SearchResult(id="2", source="memory", title="B", content="B", score=0.9),
    ]
    fts_only = [
        SearchResult(id="2", source="memory", title="B", content="B", score=1.0),
        SearchResult(id="1", source="memory", title="A", content="A", score=0.9),
    ]
    merged = search.reciprocal_rank_fusion(vector_only, fts_only)
    assert {result.id for result in merged[:2]} == {"1", "2"}


def test_hybrid_search_uses_cache(monkeypatch):
    conn = FakeSearchConnection()
    monkeypatch.setattr(
        search,
        "search_similar",
        lambda active, query_embedding, limit, scope: [
            SearchResult(id="memory-1", source="memory", title="topics/a.md", content="memory content", score=0.9)
        ],
    )

    first = search.hybrid_search(
        "test query",
        conn=conn,
        embedder=StubEmbedder(),
        now=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    second = search.hybrid_search(
        "test query",
        conn=conn,
        embedder=StubEmbedder(),
        now=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    assert first[0].id == "memory-1"
    assert second[0].id == "memory-1"
    assert conn.pruned is True
