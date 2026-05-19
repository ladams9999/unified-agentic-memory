from __future__ import annotations

from typing import Any

from .db import get_connection
from .embeddings import EmbeddingProvider, OllamaEmbeddingProvider
from .models import Memory
from .uuids import uuid7


def _memory_from_row(row: Any) -> Memory:
    return Memory(
        id=row[0],
        path=row[1],
        frontmatter=row[2] or {},
        content=row[3],
        embedding=row[4],
        created_at=row[5],
        updated_at=row[6],
    )


def upsert_memory(
    path: str,
    frontmatter: dict[str, Any],
    content: str,
    *,
    conn: Any | None = None,
    embedder: EmbeddingProvider | None = None,
) -> Memory:
    with get_connection(conn) as active:
        existing = active.execute(
            """
            SELECT id, path, frontmatter, content, embedding, created_at, updated_at
            FROM uam.memories
            WHERE path = %s
            """,
            (path,),
        ).fetchone()
        provider = embedder or OllamaEmbeddingProvider()
        embedding = existing[4] if existing and existing[3] == content else provider.embed(content)
        memory_id = existing[0] if existing else uuid7()

        active.execute(
            """
            INSERT INTO uam.memories (id, path, frontmatter, content, embedding)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (path) DO UPDATE
            SET frontmatter = EXCLUDED.frontmatter,
                content = EXCLUDED.content,
                embedding = EXCLUDED.embedding,
                updated_at = NOW()
            """,
            (memory_id, path, frontmatter, content, embedding),
        )
        if conn is None:
            active.commit()
        row = active.execute(
            """
            SELECT id, path, frontmatter, content, embedding, created_at, updated_at
            FROM uam.memories
            WHERE path = %s
            """,
            (path,),
        ).fetchone()
        return _memory_from_row(row)


def get_memory(path: str, *, conn: Any | None = None) -> Memory | None:
    with get_connection(conn) as active:
        row = active.execute(
            """
            SELECT id, path, frontmatter, content, embedding, created_at, updated_at
            FROM uam.memories
            WHERE path = %s
            """,
            (path,),
        ).fetchone()
    return _memory_from_row(row) if row else None


def delete_memory(path: str, *, conn: Any | None = None) -> bool:
    with get_connection(conn) as active:
        deleted = active.execute("DELETE FROM uam.memories WHERE path = %s", (path,)).rowcount
        if conn is None:
            active.commit()
    return bool(deleted)


def list_memories(prefix: str | None = None, *, conn: Any | None = None) -> list[Memory]:
    with get_connection(conn) as active:
        if prefix:
            rows = active.execute(
                """
                SELECT id, path, frontmatter, content, embedding, created_at, updated_at
                FROM uam.memories
                WHERE path LIKE %s
                ORDER BY path
                """,
                (f"{prefix}%",),
            ).fetchall()
        else:
            rows = active.execute(
                """
                SELECT id, path, frontmatter, content, embedding, created_at, updated_at
                FROM uam.memories
                ORDER BY path
                """
            ).fetchall()
    return [_memory_from_row(row) for row in rows]
