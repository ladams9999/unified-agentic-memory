from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel

from .config import settings
from .models import HookEvent


class QueuedEventRecord(BaseModel):
    queue_id: int
    event: HookEvent
    attempt_count: int
    status: str
    profile_name: str | None = None


def queue_path(path: Path | None = None) -> Path:
    return path or settings.local_state_path


def _connect(path: Path | None = None) -> sqlite3.Connection:
    target = queue_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row
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
            last_error TEXT,
            claimed_at TEXT,
            processed_at TEXT
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
                last_error,
                claimed_at,
                processed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', 0, NULL, NULL, NULL)
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


def claim_next_event(*, path: Path | None = None, include_failed: bool = False) -> QueuedEventRecord | None:
    conn = _connect(path)
    try:
        allowed_states = ("pending", "failed") if include_failed else ("pending",)
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            """
            SELECT queue_id, payload_json, attempt_count, status, profile_name
            FROM queued_events
            WHERE status IN ({placeholders})
            ORDER BY queue_id ASC
            LIMIT 1
            """.format(placeholders=", ".join("?" for _ in allowed_states)),
            allowed_states,
        ).fetchone()
        if row is None:
            conn.commit()
            return None
        conn.execute(
            """
            UPDATE queued_events
            SET status = 'processing',
                attempt_count = attempt_count + 1,
                claimed_at = ?,
                last_error = NULL
            WHERE queue_id = ?
            """,
            (datetime.now(timezone.utc).isoformat(), row["queue_id"]),
        )
        conn.commit()
        return QueuedEventRecord(
            queue_id=int(row["queue_id"]),
            event=HookEvent.model_validate(json.loads(row["payload_json"])),
            attempt_count=int(row["attempt_count"]) + 1,
            status="processing",
            profile_name=row["profile_name"],
        )
    finally:
        conn.close()


def mark_event_processed(queue_id: int, *, path: Path | None = None) -> None:
    conn = _connect(path)
    try:
        conn.execute(
            """
            UPDATE queued_events
            SET status = 'done',
                processed_at = ?,
                last_error = NULL
            WHERE queue_id = ?
            """,
            (datetime.now(timezone.utc).isoformat(), queue_id),
        )
        conn.commit()
    finally:
        conn.close()


def mark_event_failed(queue_id: int, error: str, *, path: Path | None = None) -> None:
    conn = _connect(path)
    try:
        conn.execute(
            """
            UPDATE queued_events
            SET status = 'failed',
                last_error = ?
            WHERE queue_id = ?
            """,
            (error, queue_id),
        )
        conn.commit()
    finally:
        conn.close()


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


def queue_status_counts(*, path: Path | None = None) -> dict[str, int]:
    conn = _connect(path)
    try:
        rows = conn.execute(
            "SELECT status, COUNT(*) AS total FROM queued_events GROUP BY status"
        ).fetchall()
        counts = {"pending": 0, "processing": 0, "failed": 0, "done": 0}
        for row in rows:
            counts[str(row["status"])] = int(row["total"])
        return counts
    finally:
        conn.close()
