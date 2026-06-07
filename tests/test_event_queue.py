from __future__ import annotations

import json

from uam.event_queue import (
    claim_next_event,
    count_queued_events,
    enqueue_event,
    mark_event_failed,
    mark_event_processed,
    queue_status_counts,
)
from uam.models import HookEvent


def test_enqueue_event_persists_normalized_payload(tmp_path, monkeypatch):
    queue_file = tmp_path / "uam.sqlite3"
    monkeypatch.setattr("uam.event_queue.settings.local_state_path", queue_file)

    queued = enqueue_event(
        HookEvent(
            client="claude-code",
            event_name="Stop",
            raw_payload={"eventName": "Stop"},
            profile_name="focus",
        )
    )

    assert queued.id is not None
    assert count_queued_events(path=queue_file) == 1

    import sqlite3

    conn = sqlite3.connect(queue_file)
    try:
        row = conn.execute(
            "SELECT event_id, profile_name, payload_json FROM queued_events"
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    assert row[0] == str(queued.id)
    assert row[1] == "focus"
    payload = json.loads(row[2])
    assert payload["event_name"] == "Stop"


def test_claim_and_mark_event_lifecycle(tmp_path, monkeypatch):
    queue_file = tmp_path / "uam.sqlite3"
    monkeypatch.setattr("uam.event_queue.settings.local_state_path", queue_file)
    enqueue_event(HookEvent(client="claude-code", event_name="Stop", raw_payload={"eventName": "Stop"}))

    queued = claim_next_event(path=queue_file)

    assert queued is not None
    assert queued.status == "processing"
    assert queue_status_counts(path=queue_file)["processing"] == 1

    mark_event_failed(queued.queue_id, "boom", path=queue_file)
    assert queue_status_counts(path=queue_file)["failed"] == 1

    queued = claim_next_event(path=queue_file, include_failed=True)
    assert queued is not None
    mark_event_processed(queued.queue_id, path=queue_file)
    assert queue_status_counts(path=queue_file)["done"] == 1
