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


def test_cwd_windows_backslashes_normalized():
    """Windows-style cwd with backslashes is stored as forward slashes."""
    payload = {
        "sessionId": "018fc5bb-53d4-7b80-95a0-e1b64116f0c0",
        "eventName": "SessionStart",
        "cwd": "C:\\Users\\test\\my-project",
    }
    event = handler.normalize_payload("claude-code", payload)
    assert event.cwd == "C:/Users/test/my-project"


def test_cwd_unix_paths_unchanged():
    """Unix-style cwd paths pass through unchanged."""
    payload = {
        "sessionId": "018fc5bb-53d4-7b80-95a0-e1b64116f0c0",
        "eventName": "SessionStart",
        "cwd": "/home/user/project",
    }
    event = handler.normalize_payload("copilot", payload)
    assert event.cwd == "/home/user/project"


def test_cwd_missing_is_none():
    """Missing cwd results in None without raising."""
    payload = {
        "sessionId": "018fc5bb-53d4-7b80-95a0-e1b64116f0c0",
        "eventName": "SessionStart",
    }
    event = handler.normalize_payload("claude-code", payload)
    assert event.cwd is None


def test_cwd_workspace_alias_normalized():
    """workspace field is used as cwd fallback and backslashes are normalized."""
    payload = {
        "sessionId": "018fc5bb-53d4-7b80-95a0-e1b64116f0c0",
        "eventName": "SessionStart",
        "workspace": "C:\\Users\\test\\workspace",
    }
    event = handler.normalize_payload("codex", payload)
    assert event.cwd == "C:/Users/test/workspace"


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
