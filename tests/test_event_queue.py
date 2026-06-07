from __future__ import annotations

import json

from uam.event_queue import count_queued_events, enqueue_event
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
