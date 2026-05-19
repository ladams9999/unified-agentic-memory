from __future__ import annotations

from typing import Any

from .graph import create_event, create_session, link_event


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
