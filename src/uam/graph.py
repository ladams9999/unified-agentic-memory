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


def ensure_path_nodes(conn: Any, path: str) -> None:
    """Create :Directory nodes for each segment of path, linked by :CHILD edges."""
    parts = [p for p in path.split("/") if p]
    for i, part in enumerate(parts[:-1]):
        segment = "/".join(parts[: i + 1])
        child_segment = "/".join(parts[: i + 2])
        _run_cypher(
            conn,
            (
                f"MERGE (parent:Directory {{path: {_quote(segment)}}}) "
                f"MERGE (child:Directory {{path: {_quote(child_segment)}}}) "
                "MERGE (parent)-[:CHILD]->(child) "
                "RETURN parent"
            ),
        )
    # Ensure the root directory node exists when path has more than one segment
    if len(parts) > 1:
        _run_cypher(
            conn,
            f"MERGE (d:Directory {{path: {_quote(parts[0])}}}) RETURN d",
        )


def upsert_memory_node(conn: Any, memory_id: uuid.UUID, path: str) -> None:
    """Create or update a :Memory node and attach it to its parent :Directory."""
    ensure_path_nodes(conn, path)
    parts = [p for p in path.split("/") if p]
    _run_cypher(
        conn,
        (
            f"MERGE (m:Memory {{path: {_quote(path)}}}) "
            f"SET m.id = {_quote(memory_id)} "
            "RETURN m"
        ),
    )
    if len(parts) > 1:
        parent_path = "/".join(parts[:-1])
        _run_cypher(
            conn,
            (
                f"MATCH (parent:Directory {{path: {_quote(parent_path)}}}), "
                f"(m:Memory {{path: {_quote(path)}}}) "
                "MERGE (parent)-[:CHILD]->(m) "
                "RETURN m"
            ),
        )


def delete_memory_node(conn: Any, path: str) -> None:
    """Remove a :Memory node and prune any :Directory nodes that become childless."""
    _run_cypher(
        conn,
        (
            f"MATCH (m:Memory {{path: {_quote(path)}}}) "
            "DETACH DELETE m "
            "RETURN m"
        ),
    )
    # Prune orphaned directory nodes bottom-up
    parts = [p for p in path.split("/") if p]
    for i in range(len(parts) - 2, -1, -1):
        segment = "/".join(parts[: i + 1])
        rows = _run_cypher(
            conn,
            (
                f"MATCH (d:Directory {{path: {_quote(segment)}}})-[:CHILD]->(child) "
                "RETURN count(child) AS c"
            ),
        )
        if rows:
            count_val = _parse_agtype(rows[0][0])
            if isinstance(count_val, dict):
                count_val = count_val.get("c", 1)
            if int(count_val) == 0:
                _run_cypher(
                    conn,
                    f"MATCH (d:Directory {{path: {_quote(segment)}}}) DETACH DELETE d RETURN d",
                )
