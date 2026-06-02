from __future__ import annotations

from typing import Any

from .graph import create_event, create_session, delete_memory_node, link_event, upsert_memory_node


def project_event(conn: Any, event_row: dict[str, Any]) -> None:
    session_id = event_row["session_id"]
    event_id = event_row["id"]
    create_session(conn, session_id, event_row["client"])
    create_event(conn, event_id, session_id, event_row["event_name"], event_row["occurred_at"])
    previous = conn.execute(
        """
        SELECT id
        FROM uam.events
        WHERE session_id = %s AND occurred_at < %s
        ORDER BY occurred_at DESC, id DESC
        LIMIT 1
        """,
        (session_id, event_row["occurred_at"]),
    ).fetchone()
    link_event(conn, session_id, event_id, previous[0] if previous else None)


def project_memory(conn: Any, memory: Any) -> None:
    upsert_memory_node(conn, memory.id, memory.path)


def remove_memory_projection(conn: Any, path: str) -> None:
    delete_memory_node(conn, path)


def replay_relational_memories(conn: Any) -> int:
    from .models import Memory, MemoryType

    rows = conn.execute(
        "SELECT id, path, frontmatter, content, memory_type, embedding, created_at, updated_at FROM uam.memories ORDER BY path"
    ).fetchall()
    total = 0
    for row in rows:
        memory = Memory(
            id=row[0],
            path=row[1],
            frontmatter=row[2] or {},
            content=row[3],
            memory_type=MemoryType(row[4]),
            embedding=row[5],
            created_at=row[6],
            updated_at=row[7],
        )
        project_memory(conn, memory)
        total += 1
    return total


def replay_relational_events(conn: Any) -> int:
    rows = conn.execute(
        """
        SELECT id, session_id, client, event_name, occurred_at
        FROM uam.events
        ORDER BY occurred_at ASC, id ASC
        """
    ).fetchall()
    total = 0
    for row in rows:
        project_event(
            conn,
            {
                "id": row[0],
                "session_id": row[1],
                "client": row[2],
                "event_name": row[3],
                "occurred_at": row[4],
            },
        )
        total += 1
    return total
