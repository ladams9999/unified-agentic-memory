from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from .db import ensure_age


def _quote(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (uuid.UUID, datetime)):
        return json.dumps(str(value))
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(str(value))


def _parse_agtype(raw: str) -> dict[str, Any]:
    payload = raw.split("::", 1)[0]
    return json.loads(payload)


def _run_cypher(conn: Any, query: str) -> list[tuple[Any, ...]]:
    ensure_age(conn)
    cursor = conn.execute(
        f"SELECT * FROM ag_catalog.cypher('uam', $$ {query} $$) AS (result agtype)"
    )
    return cursor.fetchall()


def create_session(conn: Any, session_id: uuid.UUID, client: str) -> None:
    query = (
        f"MERGE (s:Session {{id: {_quote(session_id)}}}) "
        f"SET s.client = {_quote(client)} "
        "RETURN s"
    )
    _run_cypher(conn, query)


def create_event(
    conn: Any,
    event_id: uuid.UUID,
    session_id: uuid.UUID,
    event_name: str,
    occurred_at: datetime,
) -> None:
    query = (
        f"MATCH (s:Session {{id: {_quote(session_id)}}}) "
        f"MERGE (e:Event {{id: {_quote(event_id)}}}) "
        f"SET e.event_name = {_quote(event_name)}, "
        f"    e.occurred_at = {_quote(occurred_at.isoformat())} "
        "RETURN e"
    )
    _run_cypher(conn, query)


def link_event(
    conn: Any,
    session_id: uuid.UUID,
    event_id: uuid.UUID,
    previous_event_id: uuid.UUID | None = None,
) -> None:
    _run_cypher(
        conn,
        (
            f"MATCH (s:Session {{id: {_quote(session_id)}}}), "
            f"(e:Event {{id: {_quote(event_id)}}}) "
            "MERGE (s)-[:HAS_EVENT]->(e) "
            "RETURN e"
        ),
    )
    if previous_event_id is None:
        return
    _run_cypher(
        conn,
        (
            f"MATCH (prev:Event {{id: {_quote(previous_event_id)}}}), "
            f"(curr:Event {{id: {_quote(event_id)}}}) "
            "MERGE (prev)-[:NEXT_EVENT]->(curr) "
            "RETURN curr"
        ),
    )


def get_session_events(conn: Any, session_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = _run_cypher(
        conn,
        (
            f"MATCH (:Session {{id: {_quote(session_id)}}})-[:HAS_EVENT]->(e:Event) "
            "RETURN e ORDER BY e.occurred_at, e.id"
        ),
    )
    return [_parse_agtype(row[0]) for row in rows]
