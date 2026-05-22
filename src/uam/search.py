from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Iterable

from psycopg.types.json import Jsonb

from .config import settings
from .db import get_connection
from .embeddings import EmbeddingProvider, OllamaEmbeddingProvider
from .models import SearchResult
from .vectors import search_similar


def _unwrap_json(value: Any) -> Any:
    return value.obj if hasattr(value, "obj") else value


def _hash_query(query: str, scope: str, limit: int) -> str:
    return hashlib.sha256(f"{scope}:{limit}:{query.lower()}".encode("utf-8")).hexdigest()


def _rrf_score(rank: int, k: int = 60) -> float:
    return 1.0 / (k + rank)


def reciprocal_rank_fusion(*result_sets: Iterable[SearchResult]) -> list[SearchResult]:
    merged: dict[tuple[str, str], SearchResult] = {}
    scores: dict[tuple[str, str], float] = {}
    for result_set in result_sets:
        for rank, result in enumerate(result_set, start=1):
            key = (result.source, result.id)
            merged.setdefault(key, result)
            scores[key] = scores.get(key, 0.0) + _rrf_score(rank)
    ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    final: list[SearchResult] = []
    for key, score in ordered:
        result = merged[key].model_copy()
        result.score = score
        final.append(result)
    return final


def _full_text_search(conn: Any, query: str, scope: str, limit: int) -> list[SearchResult]:
    ts_query = query
    results: list[SearchResult] = []
    if scope in {"all", "events"}:
        rows = conn.execute(
            """
            SELECT id::text, event_name, COALESCE(user_prompt, raw_payload::text),
                   ts_rank(content_tsv, websearch_to_tsquery('simple', %s)) AS score
            FROM uam.events
            WHERE content_tsv @@ websearch_to_tsquery('simple', %s)
            ORDER BY score DESC, occurred_at DESC
            LIMIT %s
            """,
            (ts_query, ts_query, limit),
        ).fetchall()
        results.extend(
            SearchResult(
                id=row[0],
                source="event",
                title=row[1],
                content=row[2],
                score=float(row[3]),
            )
            for row in rows
        )

    if scope in {"all", "memories"}:
        rows = conn.execute(
            """
            SELECT id::text, path, content,
                   ts_rank(content_tsv, websearch_to_tsquery('simple', %s)) AS score
            FROM uam.memories
            WHERE content_tsv @@ websearch_to_tsquery('simple', %s)
            ORDER BY score DESC, updated_at DESC
            LIMIT %s
            """,
            (ts_query, ts_query, limit),
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


def _get_cached_results(conn: Any, query_hash: str, now: datetime) -> list[SearchResult] | None:
    row = conn.execute(
        """
        SELECT results
        FROM uam.search_cache
        WHERE query_hash = %s
          AND created_at + (ttl_seconds || ' seconds')::interval > %s
        """,
        (query_hash, now),
    ).fetchone()
    if row is None:
        return None
    return [SearchResult.model_validate(item) for item in _unwrap_json(row[0])]


def _cache_results(
    conn: Any,
    query_hash: str,
    results: list[SearchResult],
    ttl_seconds: int,
    now: datetime,
) -> None:
    conn.execute(
        """
        DELETE FROM uam.search_cache
        WHERE created_at + (ttl_seconds || ' seconds')::interval <= %s
        """,
        (now,),
    )
    conn.execute(
        """
        INSERT INTO uam.search_cache (query_hash, results, created_at, ttl_seconds)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (query_hash) DO UPDATE
        SET results = EXCLUDED.results,
            created_at = EXCLUDED.created_at,
            ttl_seconds = EXCLUDED.ttl_seconds
        """,
        (query_hash, Jsonb([result.model_dump(mode="json") for result in results]), now, ttl_seconds),
    )


def hybrid_search(
    query: str,
    scope: str = "all",
    limit: int = 5,
    *,
    conn: Any | None = None,
    embedder: EmbeddingProvider | None = None,
    now: datetime | None = None,
) -> list[SearchResult]:
    lookup_time = now or datetime.now(timezone.utc)
    with get_connection(conn) as active:
        query_hash = _hash_query(query, scope, limit)
        cached = _get_cached_results(active, query_hash, lookup_time)
        if cached is not None:
            return cached[:limit]

        provider = embedder or OllamaEmbeddingProvider()
        vector_results = search_similar(active, provider.embed(query), limit, scope)
        fts_results = _full_text_search(active, query, scope, limit)
        merged = reciprocal_rank_fusion(vector_results, fts_results)[:limit]
        _cache_results(active, query_hash, merged, settings.search_cache_ttl_seconds, lookup_time)
        if conn is None:
            active.commit()
        return merged
