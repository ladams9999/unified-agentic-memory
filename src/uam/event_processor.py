from __future__ import annotations

from typing import Any

from .event_queue import claim_next_event, count_queued_events, mark_event_failed, mark_event_processed, queue_status_counts
from .events import log_event
from .hooks.injector import refresh_cached_responses
from .profiles import resolve_profile


def process_queued_events(*, limit: int = 50, retry_failed: bool = False) -> dict[str, Any]:
    processed = 0
    failed = 0
    for _ in range(limit):
        queued = claim_next_event(include_failed=retry_failed)
        if queued is None:
            break
        try:
            resolve_profile(queued.event.profile_name)
            log_event(queued.event)
            mark_event_processed(queued.queue_id)
            processed += 1
        except Exception as exc:  # noqa: BLE001
            mark_event_failed(queued.queue_id, str(exc))
            failed += 1
    counts = queue_status_counts()
    cache_summary = {"refreshed": 0}
    if processed:
        cache_summary = refresh_cached_responses()
    counts["processed_this_run"] = processed
    counts["failed_this_run"] = failed
    counts["remaining"] = count_queued_events() + count_queued_events(status="failed")
    counts["refreshed_cached_responses"] = cache_summary["refreshed"]
    return counts
