from __future__ import annotations

import io
import json
import sys
from pathlib import Path

from uam.hooks import handler


def test_normalize_payload_for_clients():
    payload = {
        "sessionId": "018fc5bb-53d4-7b80-95a0-e1b64116f0c0",
        "agentName": "Claude",
        "modelName": "sonnet",
        "eventName": "UserPromptSubmit",
        "userPrompt": "remember this",
        "tool": {"name": "search", "input": {"query": "test"}},
        "cwd": "C:\\repo",
    }

    claude = handler.normalize_payload("claude-code", payload)
    codex = handler.normalize_payload("codex", payload)
    copilot = handler.normalize_payload("copilot", payload)

    assert claude.client == "claude-code"
    assert codex.tool_name == "search"
    assert copilot.user_prompt == "remember this"


def test_normalize_copilot_cli_payload():
    payload = {
        "hook_event_name": "sessionStart",
        "sessionId": "018fc5bb-53d4-7b80-95a0-e1b64116f0c0",
        "timestamp": 1716400000123,
        "cwd": "C:\\repo",
        "toolName": "view",
        "toolArgs": {"path": "README.md"},
    }

    event = handler.normalize_payload("copilot", payload)

    assert event.event_name == "SessionStart"
    assert event.tool_name == "view"
    assert event.tool_input == {"path": "README.md"}
    assert event.occurred_at.isoformat() == "2024-05-22T17:46:40.123000+00:00"


def test_handler_exits_zero_and_logs(monkeypatch, tmp_path):
    monkeypatch.setattr(handler.settings, "local_log_dir", tmp_path)
    def fail_log_event(event):
        raise RuntimeError("boom")

    monkeypatch.setattr(handler, "log_event", fail_log_event)
    stdin = Path(tmp_path / "payload.json")
    stdin.write_text(json.dumps({"eventName": "Stop"}), encoding="utf-8")

    with stdin.open("r", encoding="utf-8") as handle:
        monkeypatch.setattr(sys, "stdin", handle)
        code = handler.run(["--client", "claude-code"])

    assert code == 0
    assert (tmp_path / "hook-handler.log").exists()
    assert (tmp_path / "hook_metrics_summary.json").exists()


def test_copilot_session_start_uses_additional_context(monkeypatch, capsys):
    monkeypatch.setattr(handler, "log_event", lambda event: None)
    monkeypatch.setattr(
        handler,
        "session_start_payload",
        lambda client: {"system": "profile memory"},
    )

    stdin = json.dumps(
        {
            "hook_event_name": "sessionStart",
            "sessionId": "018fc5bb-53d4-7b80-95a0-e1b64116f0c0",
            "timestamp": 1716400000123,
            "cwd": "C:\\repo",
        }
    )
    monkeypatch.setattr(sys, "stdin", io.StringIO(stdin))

    code = handler.run(["--client", "copilot"])
    output = capsys.readouterr().out.strip()

    assert code == 0
    assert output == '{"additionalContext": "profile memory"}'
