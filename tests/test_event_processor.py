from __future__ import annotations

from uam.event_processor import process_queued_events
from uam.event_queue import count_queued_events, enqueue_event, queue_status_counts
from uam.models import HookEvent


def test_process_queued_events_marks_done(tmp_path, monkeypatch):
    queue_file = tmp_path / "uam.sqlite3"
    monkeypatch.setattr("uam.event_queue.settings.local_state_path", queue_file)
    monkeypatch.setattr("uam.event_processor.resolve_profile", lambda profile_name=None: object())
    processed = []
    monkeypatch.setattr("uam.event_processor.log_event", lambda event: processed.append(event))

    enqueue_event(HookEvent(client="claude-code", event_name="Stop", raw_payload={"eventName": "Stop"}))
    result = process_queued_events(limit=5)

    assert len(processed) == 1
    assert result["processed_this_run"] == 1
    assert queue_status_counts(path=queue_file)["done"] == 1


def test_process_queued_events_marks_failed_on_profile_error(tmp_path, monkeypatch):
    queue_file = tmp_path / "uam.sqlite3"
    monkeypatch.setattr("uam.event_queue.settings.local_state_path", queue_file)
    monkeypatch.setattr(
        "uam.event_processor.resolve_profile",
        lambda profile_name=None: (_ for _ in ()).throw(ValueError("Unknown profile")),
    )

    enqueue_event(
        HookEvent(
            client="claude-code",
            event_name="Stop",
            raw_payload={"eventName": "Stop"},
            profile_name="missing",
        )
    )
    result = process_queued_events(limit=5)

    assert result["failed_this_run"] == 1
    assert queue_status_counts(path=queue_file)["failed"] == 1
    assert count_queued_events(path=queue_file, status="failed") == 1
