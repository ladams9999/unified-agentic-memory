from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from pgvector.psycopg import register_vector
from psycopg_pool import ConnectionPool

from .config import settings

_POOL: ConnectionPool | None = None


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def migrations_dir() -> Path:
    return project_root() / "db_stack" / "migrations"


def configure_pool(conninfo: str | None = None) -> ConnectionPool:
    global _POOL
    _POOL = ConnectionPool(conninfo=conninfo or settings.database_url, open=False)
    _POOL.open()
    return _POOL


def get_pool() -> ConnectionPool:
    global _POOL
    if _POOL is None:
        return configure_pool()
    if _POOL.closed:
        _POOL.open()
    return _POOL


def close_pool() -> None:
    global _POOL
    if _POOL is not None and not _POOL.closed:
        _POOL.close()


@contextmanager
def get_connection(existing: Any | None = None) -> Iterator[Any]:
    if existing is not None:
        yield existing
        return

    pool = get_pool()
    with pool.connection() as conn:
        register_vector(conn)
        yield conn


def ensure_age(conn: Any) -> None:
    conn.execute("LOAD 'age'")
    conn.execute('SET search_path = ag_catalog, "$user", public')


def apply_migrations(conn: Any, directory: Path | None = None) -> list[str]:
    conn.execute("CREATE SCHEMA IF NOT EXISTS uam")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS uam.schema_migrations (
            filename TEXT PRIMARY KEY,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    applied = {
        row[0]
        for row in conn.execute(
            "SELECT filename FROM uam.schema_migrations ORDER BY filename"
        ).fetchall()
    }
    applied_now: list[str] = []
    for path in sorted((directory or migrations_dir()).glob("*.sql")):
        if path.name in applied:
            continue
        conn.execute(path.read_text(encoding="utf-8"))
        conn.execute(
            "INSERT INTO uam.schema_migrations (filename) VALUES (%s)",
            (path.name,),
        )
        applied_now.append(path.name)
    return applied_now
