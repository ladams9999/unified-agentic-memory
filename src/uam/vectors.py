from __future__ import annotations

import uuid
from typing import Any

from pgvector import Vector
from psycopg.types.json import Jsonb

from .models import SearchResult
from .uuids import uuid7


def store_embedding(
    conn: Any,
    *,
    event_id: uuid.UUID,
    content: str,
    embedding: list[float],
    metadata: dict[str, Any] | None = None,
) -> uuid.UUID:
    embedding_id = uuid7()
    conn.execute(
        """
        INSERT INTO uam.embeddings (id, event_id, embedding, content, metadata)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (embedding_id, event_id, embedding, content, Jsonb(metadata or {})),
    )
    return embedding_id


def search_similar(
    conn: Any,
    query_embedding: list[float],
    limit: int,
    scope: str = "all",
) -> list[SearchResult]:
    results: list[SearchResult] = []
    query_vector = Vector(query_embedding)
    if scope in {"all", "events"}:
        rows = conn.execute(
            """
            SELECT e.id::text, ev.event_name, e.content, 1 - (e.embedding <=> %s) AS score, ev.client
            FROM uam.embeddings e
            JOIN uam.events ev ON ev.id = e.event_id
            ORDER BY e.embedding <=> %s
            LIMIT %s
            """,
            (query_vector, query_vector, limit),
        ).fetchall()
        results.extend(
            SearchResult(
                id=row[0],
                source="event",
                title=row[1],
                content=row[2],
                score=float(row[3]),
                metadata={"client": row[4]},
            )
            for row in rows
        )

    if scope in {"all", "memories"}:
        rows = conn.execute(
            """
            SELECT id::text, path, content, 1 - (embedding <=> %s) AS score
            FROM uam.memories
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> %s
            LIMIT %s
            """,
            (query_vector, query_vector, limit),
        ).fetchall()
        results.extend(
            SearchResult(
                id=row[0],
                source="memory",
                path=row[1],
                title=row[1],
                content=row[2],
                score=float(row[3]),
            )
            for row in rows
        )
    return results
