from __future__ import annotations

from typing import Any

from psycopg.types.json import Jsonb

from .db import get_connection
from .embeddings import EmbeddingProvider, get_embedding_provider
from .models import HookEvent
from .projection import project_event
from .vectors import store_embedding


def log_event(
    hook_event: HookEvent,
    *,
    conn: Any | None = None,
    embedder: EmbeddingProvider | None = None,
) -> HookEvent:
    event = hook_event.with_identifiers()
    with get_connection(conn) as active:
        active.execute(
            """
            INSERT INTO uam.events (
                id,
                session_id,
                client,
                agent_name,
                model_name,
                event_name,
                tool_name,
                tool_input,
                user_prompt,
                cwd,
                raw_payload,
                payload_schema_version,
                occurred_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                event.id,
                event.session_id,
                event.client,
                event.agent_name,
                event.model_name,
                event.event_name,
                event.tool_name,
                Jsonb(event.tool_input) if event.tool_input is not None else None,
                event.user_prompt,
                event.cwd,
                Jsonb(event.raw_payload),
                event.payload_schema_version,
                event.occurred_at,
            ),
        )
        if conn is None:
            active.commit()
        project_event(
            active,
            {
                "id": event.id,
                "session_id": event.session_id,
                "client": event.client,
                "event_name": event.event_name,
                "occurred_at": event.occurred_at,
            },
        )
        content = event.embedding_text()
        if content:
            provider = embedder or get_embedding_provider()
            store_embedding(
                active,
                event_id=event.id,
                content=content,
                embedding=provider.embed(content),
                metadata={"client": event.client, "event_name": event.event_name},
            )
        if conn is None:
            active.commit()
    return event


def list_session_summaries(*, conn: Any | None = None, limit: int = 20) -> list[dict[str, Any]]:
    with get_connection(conn) as active:
        rows = active.execute(
            """
            SELECT session_id, client, agent_name, model_name, MIN(occurred_at), COUNT(*)
            FROM uam.events
            GROUP BY session_id, client, agent_name, model_name
            ORDER BY MIN(occurred_at) DESC
            LIMIT %s
            """,
            (limit,),
        ).fetchall()
    return [
        {
            "session_id": str(row[0]),
            "client": row[1],
            "agent_name": row[2],
            "model_name": row[3],
            "started_at": row[4].isoformat(),
            "event_count": row[5],
        }
        for row in rows
    ]
