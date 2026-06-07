from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .config import settings
from .models import HookEvent


def queue_path(path: Path | None = None) -> Path:
    return path or settings.local_state_path


def _connect(path: Path | None = None) -> sqlite3.Connection:
    target = queue_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS queued_events (
            queue_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            client TEXT NOT NULL,
            event_name TEXT NOT NULL,
            profile_name TEXT,
            payload_json TEXT NOT NULL,
            enqueued_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            attempt_count INTEGER NOT NULL DEFAULT 0,
            last_error TEXT
        )
        """
    )
    return conn


def enqueue_event(event: HookEvent, *, path: Path | None = None) -> HookEvent:
    queued = event.with_identifiers()
    conn = _connect(path)
    try:
        conn.execute(
            """
            INSERT INTO queued_events (
                event_id,
                session_id,
                client,
                event_name,
                profile_name,
                payload_json,
                enqueued_at,
                status,
                attempt_count,
                last_error
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', 0, NULL)
            """,
            (
                str(queued.id),
                str(queued.session_id),
                queued.client,
                queued.event_name,
                queued.profile_name,
                json.dumps(queued.model_dump(mode="json")),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return queued


def count_queued_events(*, status: str = "pending", path: Path | None = None) -> int:
    conn = _connect(path)
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM queued_events WHERE status = ?",
            (status,),
        ).fetchone()
        return int(row[0]) if row else 0
    finally:
        conn.close()
