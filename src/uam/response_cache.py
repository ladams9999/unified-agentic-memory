from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel

from .config import settings


class CachedResponse(BaseModel):
    cache_key: str
    kind: str
    client: str
    profile_name: str | None = None
    query_text: str | None = None
    response_text: str
    updated_at: str


def cache_path(path: Path | None = None) -> Path:
    return path or settings.local_state_path


def _connect(path: Path | None = None) -> sqlite3.Connection:
    target = cache_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cached_responses (
            cache_key TEXT PRIMARY KEY,
            kind TEXT NOT NULL,
            client TEXT NOT NULL,
            profile_name TEXT,
            query_text TEXT,
            response_text TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    return conn


def _cache_key(kind: str, client: str, profile_name: str | None, query_text: str | None = None) -> str:
    return "::".join(
        [
            kind,
            client,
            profile_name or "",
            query_text or "",
        ]
    )


def get_cached_response(
    *,
    kind: str,
    client: str,
    profile_name: str | None = None,
    query_text: str | None = None,
    path: Path | None = None,
) -> str | None:
    conn = _connect(path)
    try:
        row = conn.execute(
            "SELECT response_text FROM cached_responses WHERE cache_key = ?",
            (_cache_key(kind, client, profile_name, query_text),),
        ).fetchone()
        return str(row["response_text"]) if row else None
    finally:
        conn.close()


def upsert_cached_response(
    *,
    kind: str,
    client: str,
    response_text: str,
    profile_name: str | None = None,
    query_text: str | None = None,
    path: Path | None = None,
) -> CachedResponse:
    updated_at = datetime.now(timezone.utc).isoformat()
    cache_key = _cache_key(kind, client, profile_name, query_text)
    conn = _connect(path)
    try:
        conn.execute(
            """
            INSERT INTO cached_responses (cache_key, kind, client, profile_name, query_text, response_text, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (cache_key) DO UPDATE
            SET response_text = EXCLUDED.response_text,
                updated_at = EXCLUDED.updated_at
            """,
            (cache_key, kind, client, profile_name, query_text, response_text, updated_at),
        )
        conn.commit()
    finally:
        conn.close()
    return CachedResponse(
        cache_key=cache_key,
        kind=kind,
        client=client,
        profile_name=profile_name,
        query_text=query_text,
        response_text=response_text,
        updated_at=updated_at,
    )


def list_cached_responses(path: Path | None = None) -> list[CachedResponse]:
    conn = _connect(path)
    try:
        rows = conn.execute(
            "SELECT cache_key, kind, client, profile_name, query_text, response_text, updated_at FROM cached_responses ORDER BY cache_key"
        ).fetchall()
        return [
            CachedResponse(
                cache_key=str(row["cache_key"]),
                kind=str(row["kind"]),
                client=str(row["client"]),
                profile_name=row["profile_name"],
                query_text=row["query_text"],
                response_text=str(row["response_text"]),
                updated_at=str(row["updated_at"]),
            )
            for row in rows
        ]
    finally:
        conn.close()
