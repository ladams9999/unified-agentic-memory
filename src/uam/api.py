from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query

from .db import get_connection
from .dream import run_dream
from .events import list_session_summaries
from .memories import delete_memory, get_memory, list_memories, upsert_memory
from .search import hybrid_search

app = FastAPI(title="Unified Agentic Memory")


@app.get("/memories")
def api_list_memories(prefix: str | None = None) -> list[dict]:
    return [memory.model_dump(mode="json") for memory in list_memories(prefix)]


@app.post("/memories")
def api_store_memory(payload: dict) -> dict:
    return upsert_memory(
        payload["path"],
        payload.get("frontmatter", {}),
        payload.get("content", ""),
    ).model_dump(mode="json")


@app.get("/memories/{path:path}")
def api_get_memory(path: str) -> dict:
    memory = get_memory(path)
    if memory is None:
        raise HTTPException(status_code=404, detail="Memory not found")
    return memory.model_dump(mode="json")


@app.delete("/memories/{path:path}")
def api_delete_memory(path: str) -> dict:
    return {"deleted": delete_memory(path)}


@app.get("/search")
def api_search(
    query: str = Query(...),
    scope: str = Query("all"),
    limit: int = Query(5, ge=1, le=50),
) -> list[dict]:
    return [result.model_dump(mode="json") for result in hybrid_search(query, scope, limit)]


@app.get("/sessions")
def api_sessions(limit: int = Query(20, ge=1, le=100)) -> list[dict]:
    return list_session_summaries(limit=limit)


@app.get("/sessions/{session_id}/events")
def api_session_events(session_id: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, event_name, tool_name, user_prompt, occurred_at, raw_payload
            FROM uam.events
            WHERE session_id = %s
            ORDER BY occurred_at ASC
            """,
            (session_id,),
        ).fetchall()
    return [
        {
            "id": str(row[0]),
            "event_name": row[1],
            "tool_name": row[2],
            "user_prompt": row[3],
            "occurred_at": row[4].isoformat(),
            "raw_payload": row[5],
        }
        for row in rows
    ]


@app.get("/stats")
def api_stats() -> dict:
    with get_connection() as conn:
        events = conn.execute("SELECT COUNT(*) FROM uam.events").fetchone()[0]
        memories = conn.execute("SELECT COUNT(*) FROM uam.memories").fetchone()[0]
        dreams = conn.execute("SELECT COUNT(*) FROM uam.dream_runs").fetchone()[0]
    return {"events": events, "memories": memories, "dream_runs": dreams}


@app.post("/dream")
def api_dream(dry_run: bool = False) -> dict:
    return run_dream(dry_run=dry_run).model_dump(mode="json")
