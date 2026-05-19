from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import settings
from ..events import log_event
from ..models import HookEvent
from .metrics import record_metric


def _pick(payload: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in payload and payload[key] not in (None, ""):
            return payload[key]
    return None


def normalize_payload(client: str, payload: dict[str, Any]) -> HookEvent:
    tool = payload.get("tool") or payload.get("toolUse") or {}
    occurred_at = _pick(payload, "occurred_at", "occurredAt", "timestamp")
    event = HookEvent(
        session_id=_pick(payload, "session_id", "sessionId"),
        client=client,
        agent_name=_pick(payload, "agent_name", "agentName", "agent"),
        model_name=_pick(payload, "model_name", "modelName", "model"),
        event_name=_pick(payload, "event_name", "eventName", "hookEvent", "event") or "unknown",
        tool_name=_pick(tool, "name", "tool_name", "toolName"),
        tool_input=_pick(tool, "input", "arguments", "payload"),
        user_prompt=_pick(payload, "user_prompt", "userPrompt", "prompt"),
        cwd=_pick(payload, "cwd", "workspace", "workingDirectory"),
        raw_payload=payload,
        occurred_at=datetime.fromisoformat(occurred_at) if occurred_at else datetime.now(timezone.utc),
    )
    if event.session_id is None:
        warning = {"warning": "session_id missing; generated during ingest"}
        _write_log("warning", client, event.event_name, warning)
        event = event.with_identifiers()
    return event


def _write_log(level: str, client: str, event_name: str, message: Any) -> None:
    settings.local_log_dir.mkdir(parents=True, exist_ok=True)
    line = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "client": client,
        "event_name": event_name,
        "message": message,
    }
    path = Path(settings.local_log_dir) / "hook-handler.log"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(line) + "\n")


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--client", required=True)
    args = parser.parse_args(argv)

    start = time.perf_counter()
    event_name = "unknown"
    success = False
    try:
        payload = json.load(sys.stdin)
        event = normalize_payload(args.client, payload)
        event_name = event.event_name
        try:
            log_event(event)
            success = True
        except Exception as exc:  # noqa: BLE001
            _write_log("error", args.client, event_name, {"error": str(exc)})
    except Exception as exc:  # noqa: BLE001
        _write_log("error", args.client, event_name, {"error": str(exc)})
    finally:
        duration_ms = (time.perf_counter() - start) * 1000
        record_metric(args.client, event_name, duration_ms, success)
    return 0


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
