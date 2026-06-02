from __future__ import annotations

from typing import Any

from psycopg.types.json import Jsonb

from .db import get_connection
from .embeddings import EmbeddingProvider, OllamaEmbeddingProvider
from .models import Memory, MemoryType
from .projection import project_memory, remove_memory_projection
from .uuids import uuid7

_SELECT_COLS = "id, path, frontmatter, content, memory_type, embedding, created_at, updated_at"


def _unwrap_json(value: Any) -> Any:
    return value.obj if hasattr(value, "obj") else value


def _memory_from_row(row: Any) -> Memory:
    return Memory(
        id=row[0],
        path=row[1],
        frontmatter=_unwrap_json(row[2]) or {},
        content=row[3],
        memory_type=MemoryType(row[4]),
        embedding=row[5],
        created_at=row[6],
        updated_at=row[7],
    )


def upsert_memory(
    path: str,
    frontmatter: dict[str, Any],
    content: str,
    *,
    memory_type: MemoryType = MemoryType.learning,
    conn: Any | None = None,
    embedder: EmbeddingProvider | None = None,
) -> Memory:
    with get_connection(conn) as active:
        existing = active.execute(
            f"SELECT {_SELECT_COLS} FROM uam.memories WHERE path = %s",
            (path,),
        ).fetchone()
        if existing and existing[4] == MemoryType.fact.value:
            raise ValueError(f"Cannot overwrite fact memory at path '{path}'")
        provider = embedder or OllamaEmbeddingProvider()
        embedding = existing[5] if existing and existing[3] == content else provider.embed(content)
        memory_id = existing[0] if existing else uuid7()

        active.execute(
            """
            INSERT INTO uam.memories (id, path, frontmatter, content, memory_type, embedding)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (path) DO UPDATE
            SET frontmatter = EXCLUDED.frontmatter,
                content = EXCLUDED.content,
                memory_type = EXCLUDED.memory_type,
                embedding = EXCLUDED.embedding,
                updated_at = NOW()
            """,
            (memory_id, path, Jsonb(frontmatter), content, memory_type.value, embedding),
        )
        if conn is None:
            active.commit()
        row = active.execute(
            f"SELECT {_SELECT_COLS} FROM uam.memories WHERE path = %s",
            (path,),
        ).fetchone()
        memory = _memory_from_row(row)
        try:
            project_memory(active, memory)
        except Exception:
            pass
        return memory


def confirm_idea(path: str, *, conn: Any | None = None) -> Memory:
    with get_connection(conn) as active:
        row = active.execute(
            f"SELECT {_SELECT_COLS} FROM uam.memories WHERE path = %s",
            (path,),
        ).fetchone()
        if row is None:
            raise ValueError(f"Memory not found: '{path}'")
        if row[4] != MemoryType.idea.value:
            raise ValueError(f"Memory at '{path}' is not an idea (type: {row[4]})")
        active.execute(
            "UPDATE uam.memories SET memory_type = 'learning', updated_at = NOW() WHERE path = %s",
            (path,),
        )
        if conn is None:
            active.commit()
        row = active.execute(
            f"SELECT {_SELECT_COLS} FROM uam.memories WHERE path = %s",
            (path,),
        ).fetchone()
    return _memory_from_row(row)


def get_memory(path: str, *, conn: Any | None = None) -> Memory | None:
    with get_connection(conn) as active:
        row = active.execute(
            f"SELECT {_SELECT_COLS} FROM uam.memories WHERE path = %s",
            (path,),
        ).fetchone()
    return _memory_from_row(row) if row else None


def delete_memory(path: str, *, conn: Any | None = None) -> bool:
    with get_connection(conn) as active:
        deleted = active.execute("DELETE FROM uam.memories WHERE path = %s", (path,)).rowcount
        if deleted:
            try:
                remove_memory_projection(active, path)
            except Exception:
                pass
        if conn is None:
            active.commit()
    return bool(deleted)


def list_memories(prefix: str | None = None, *, conn: Any | None = None) -> list[Memory]:
    with get_connection(conn) as active:
        if prefix:
            rows = active.execute(
                f"SELECT {_SELECT_COLS} FROM uam.memories WHERE path LIKE %s ORDER BY path",
                (f"{prefix}%",),
            ).fetchall()
        else:
            rows = active.execute(
                f"SELECT {_SELECT_COLS} FROM uam.memories ORDER BY path"
            ).fetchall()
    return [_memory_from_row(row) for row in rows]
