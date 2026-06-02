from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest


class FakeResult:
    def __init__(self, rows: list[Any] | None = None, rowcount: int = 0) -> None:
        self._rows = rows or []
        self.rowcount = rowcount

    def fetchone(self) -> Any:
        return self._rows[0] if self._rows else None

    def fetchall(self) -> list[Any]:
        return list(self._rows)


class FakeMemoryConnection:
    def __init__(self) -> None:
        self.memories: dict[str, dict[str, Any]] = {}

    def execute(self, query: str, params: tuple[Any, ...] | None = None) -> FakeResult:
        params = params or ()
        if "WHERE path = %s" in query and "memory_type" in query and "SELECT" in query:
            row = self.memories.get(params[0])
            return FakeResult([self._row(row)] if row else [])
        if "UPDATE uam.memories SET memory_type" in query:
            path = params[0]
            if path in self.memories:
                self.memories[path]["memory_type"] = "learning"
            return FakeResult(rowcount=1)
        if "WHERE path LIKE %s" in query:
            prefix = params[0].rstrip("%")
            rows = [self._row(value) for key, value in sorted(self.memories.items()) if key.startswith(prefix)]
            return FakeResult(rows)
        if "FROM uam.memories ORDER BY path" in query:
            return FakeResult([self._row(value) for _, value in sorted(self.memories.items())])
        if "INSERT INTO uam.memories" in query:
            memory_id, path, frontmatter, content, memory_type, embedding = params
            now = datetime.now(timezone.utc)
            existing = self.memories.get(path)
            created_at = existing["created_at"] if existing else now
            self.memories[path] = {
                "id": memory_id,
                "path": path,
                "frontmatter": frontmatter,
                "content": content,
                "memory_type": memory_type,
                "embedding": embedding,
                "created_at": created_at,
                "updated_at": now,
            }
            return FakeResult(rowcount=1)
        if "DELETE FROM uam.memories" in query:
            deleted = 1 if self.memories.pop(params[0], None) else 0
            return FakeResult(rowcount=deleted)
        raise AssertionError(f"Unexpected query: {query}")

    def commit(self) -> None:
        return None

    @staticmethod
    def _row(row: dict[str, Any] | None) -> Any:
        if row is None:
            return None
        return (
            row["id"],
            row["path"],
            row["frontmatter"],
            row["content"],
            row.get("memory_type", "learning"),
            row["embedding"],
            row["created_at"],
            row["updated_at"],
        )


@pytest.fixture()
def fake_memory_conn() -> FakeMemoryConnection:
    return FakeMemoryConnection()
