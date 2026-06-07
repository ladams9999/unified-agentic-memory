from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import settings
from ..db import close_pool
from ..event_queue import enqueue_event
from ..models import HookEvent
from .injector import session_start_payload, user_prompt_payload
from .metrics import record_metric


def _pick(payload: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in payload and payload[key] not in (None, ""):
            return payload[key]
    return None


def _normalize_path(value: Any) -> Any:
    """Return *value* with backslashes replaced by forward slashes.

    Only acts on strings; passes anything else through unchanged so the
    function is safe to call on arbitrary payload fields.
    """
    if isinstance(value, str):
        return value.replace("\\", "/")
    return value


def _normalize_event_name(value: Any) -> str:
    if not isinstance(value, str) or not value:
        return "unknown"
    aliases = {
        "sessionstart": "SessionStart",
        "sessionend": "SessionEnd",
        "userpromptsubmit": "UserPromptSubmit",
        "userpromptsubmitted": "UserPromptSubmit",
        "pretooluse": "PreToolUse",
        "posttooluse": "PostToolUse",
        "posttoolusefailure": "PostToolUseFailure",
        "stop": "Stop",
        "agentstop": "Stop",
        "subagentstop": "SubagentStop",
        "erroroccurred": "ErrorOccurred",
        "precompact": "PreCompact",
    }
    return aliases.get(value.replace("_", "").replace("-", "").lower(), value)


def _parse_occurred_at(value: Any) -> datetime:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc)
    if isinstance(value, str) and value:
        if value.isdigit():
            return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)
        return datetime.fromisoformat(value)
    return datetime.now(timezone.utc)


def _tool_payload(payload: dict[str, Any]) -> dict[str, Any]:
    tool = payload.get("tool") or payload.get("toolUse")
    if isinstance(tool, dict):
        return tool
    return payload


def _copilot_injection(event: HookEvent) -> dict[str, str] | None:
    if event.event_name != "SessionStart":
        return None
    payload = session_start_payload(event.client, profile_name=event.profile_name)
    return {"additionalContext": payload["system"]}


def normalize_payload(client: str, payload: dict[str, Any]) -> HookEvent:
    tool = _tool_payload(payload)
    occurred_at = _pick(payload, "occurred_at", "occurredAt", "timestamp")
    event = HookEvent(
        session_id=_pick(payload, "session_id", "sessionId"),
        client=client,
        agent_name=_pick(payload, "agent_name", "agentName", "agent"),
        model_name=_pick(payload, "model_name", "modelName", "model"),
        event_name=_normalize_event_name(
            _pick(payload, "hook_event_name", "event_name", "eventName", "hookEvent", "event")
        ),
        tool_name=_pick(tool, "name", "tool_name", "toolName"),
        tool_input=_pick(tool, "input", "arguments", "payload", "tool_input", "toolArgs"),
        user_prompt=_pick(payload, "user_prompt", "userPrompt", "prompt"),
        cwd=_normalize_path(_pick(payload, "cwd", "workspace", "workingDirectory")),
        raw_payload=payload,
        occurred_at=_parse_occurred_at(occurred_at),
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


def _spawn_processor() -> None:
    command = [sys.executable, "-m", "uam.cli", "process-events", "--limit", "25"]
    kwargs: dict[str, Any] = {
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "cwd": Path(__file__).resolve().parents[3],
        "start_new_session": True,
    }
    if hasattr(subprocess, "CREATE_NO_WINDOW"):
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    subprocess.Popen(command, **kwargs)


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--client", required=True)
    parser.add_argument("--profile")
    args = parser.parse_args(argv)

    start = time.perf_counter()
    event_name = "unknown"
    success = False
    try:
        payload = json.load(sys.stdin)
        event = normalize_payload(args.client, payload)
        event.profile_name = args.profile
        event_name = event.event_name
        try:
            enqueue_event(event)
            success = True
            try:
                _spawn_processor()
            except Exception as exc:  # noqa: BLE001
                _write_log("warning", args.client, event_name, {"processor_error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            _write_log("error", args.client, event_name, {"error": str(exc)})

        injection: dict | None = None
        try:
            if args.client == "copilot":
                injection = _copilot_injection(event)
            elif event.event_name == "SessionStart":
                injection = session_start_payload(args.client, profile_name=args.profile)
            elif event.event_name == "UserPromptSubmit" and event.user_prompt:
                injection = user_prompt_payload(args.client, event.user_prompt, profile_name=args.profile)
        except Exception as exc:  # noqa: BLE001
            _write_log("error", args.client, event_name, {"injection_error": str(exc)})

        if injection is not None:
            print(json.dumps(injection))
    except Exception as exc:  # noqa: BLE001
        _write_log("error", args.client, event_name, {"error": str(exc)})
    finally:
        duration_ms = (time.perf_counter() - start) * 1000
        record_metric(args.client, event_name, duration_ms, success)
        close_pool()
    return 0


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
