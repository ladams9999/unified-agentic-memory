from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import settings


def _log_dir() -> Path:
    settings.local_log_dir.mkdir(parents=True, exist_ok=True)
    return settings.local_log_dir


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    index = max(0, min(len(values) - 1, round((percentile / 100) * (len(values) - 1))))
    return values[index]


def summarize_metrics(entries: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    grouped: dict[str, list[float]] = {}
    for entry in entries:
        key = f"{entry['client']}:{entry['event_name']}"
        grouped.setdefault(key, []).append(float(entry["duration_ms"]))
    return {
        key: {
            "count": float(len(values)),
            "p50_ms": _percentile(values, 50),
            "p95_ms": _percentile(values, 95),
        }
        for key, values in grouped.items()
    }


def record_metric(client: str, event_name: str, duration_ms: float, success: bool) -> dict[str, dict[str, float]]:
    metric = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "client": client,
        "event_name": event_name,
        "duration_ms": duration_ms,
        "success": success,
    }
    metrics_path = _log_dir() / "hook_metrics.jsonl"
    with metrics_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(metric) + "\n")

    entries = [
        json.loads(line)
        for line in metrics_path.read_text(encoding="utf-8").splitlines()[-settings.hook_metrics_window :]
        if line.strip()
    ]
    summary = summarize_metrics(entries)
    (_log_dir() / "hook_metrics_summary.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )
    return summary
