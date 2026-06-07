from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from uam.cli import app


runner = CliRunner()


def _make_uam_hooks(tmp_path: Path, client: str, content: str | None = None) -> Path:
    """Create a minimal UAM hook template file in a fake UAM repo structure."""
    dest_map = {
        "copilot": "hooks/copilot/hooks.json",
        "claude-code": "hooks/claude-code/settings.json",
        "codex": "hooks/codex/hooks.json",
    }
    tmpl_path = tmp_path / "uam_root" / dest_map[client]
    tmpl_path.parent.mkdir(parents=True, exist_ok=True)
    if content is None:
        content = json.dumps({"placeholder": "<UAM_PROJECT_DIR>"})
    tmpl_path.write_text(content, encoding="utf-8")
    return tmp_path / "uam_root"


def _target(tmp_path: Path) -> Path:
    t = tmp_path / "target_project"
    t.mkdir()
    return t


def test_install_hooks_unknown_client(tmp_path):
    target = _target(tmp_path)
    result = runner.invoke(app, ["install-hooks", "--client", "unknown", "--target-dir", str(target)])
    assert result.exit_code != 0
    assert "Unknown client" in result.output


def test_install_hooks_copilot_creates_file(tmp_path, monkeypatch):
    uam_root = _make_uam_hooks(tmp_path, "copilot", '{"cwd": "<UAM_PROJECT_DIR>"}')
    target = _target(tmp_path)
    monkeypatch.setattr("uam.cli.project_root", lambda: uam_root)

    result = runner.invoke(app, ["install-hooks", "--client", "copilot", "--target-dir", str(target)])

    assert result.exit_code == 0, result.output
    dest = target / ".github" / "hooks" / "uam-memory.json"
    assert dest.exists()
    # placeholder should be replaced; no backslashes in the substituted value
    written = dest.read_text(encoding="utf-8")
    assert "<UAM_PROJECT_DIR>" not in written
    assert "\\" not in written


def test_install_hooks_claude_code_creates_file(tmp_path, monkeypatch):
    uam_root = _make_uam_hooks(tmp_path, "claude-code", '{"dir": "<UAM_PROJECT_DIR>"}')
    target = _target(tmp_path)
    monkeypatch.setattr("uam.cli.project_root", lambda: uam_root)

    result = runner.invoke(app, ["install-hooks", "--client", "claude-code", "--target-dir", str(target)])

    assert result.exit_code == 0, result.output
    dest = target / ".claude" / "settings.json"
    assert dest.exists()


def test_install_hooks_codex_creates_file(tmp_path, monkeypatch):
    uam_root = _make_uam_hooks(tmp_path, "codex", '{"dir": "<UAM_PROJECT_DIR>"}')
    target = _target(tmp_path)
    monkeypatch.setattr("uam.cli.project_root", lambda: uam_root)

    result = runner.invoke(app, ["install-hooks", "--client", "codex", "--target-dir", str(target)])

    assert result.exit_code == 0, result.output
    dest = target / ".codex" / "hooks.json"
    assert dest.exists()


def test_install_hooks_idempotent_same_content(tmp_path, monkeypatch):
    """Re-running with identical content should report 'already up to date'."""
    uam_root = _make_uam_hooks(tmp_path, "copilot", '{"cwd": "<UAM_PROJECT_DIR>"}')
    target = _target(tmp_path)
    monkeypatch.setattr("uam.cli.project_root", lambda: uam_root)

    runner.invoke(app, ["install-hooks", "--client", "copilot", "--target-dir", str(target)])
    result = runner.invoke(app, ["install-hooks", "--client", "copilot", "--target-dir", str(target)])

    assert result.exit_code == 0
    assert "already up to date" in result.output.lower()


def test_install_hooks_warns_on_conflicting_content(tmp_path, monkeypatch):
    """If destination exists with different content, warn and exit non-zero."""
    uam_root = _make_uam_hooks(tmp_path, "copilot", '{"cwd": "<UAM_PROJECT_DIR>"}')
    target = _target(tmp_path)
    monkeypatch.setattr("uam.cli.project_root", lambda: uam_root)

    # Pre-create the destination with different content.
    dest = target / ".github" / "hooks" / "uam-memory.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text('{"different": true}', encoding="utf-8")

    result = runner.invoke(app, ["install-hooks", "--client", "copilot", "--target-dir", str(target)])

    assert result.exit_code != 0
    assert "WARNING" in result.output


def test_install_hooks_substitutes_uam_root_forward_slashes(tmp_path, monkeypatch):
    """UAM root path in output must use forward slashes even on Windows."""
    uam_root = _make_uam_hooks(tmp_path, "codex", '"<UAM_PROJECT_DIR>"')
    target = _target(tmp_path)
    monkeypatch.setattr("uam.cli.project_root", lambda: uam_root)

    runner.invoke(app, ["install-hooks", "--client", "codex", "--target-dir", str(target)])
    dest = target / ".codex" / "hooks.json"
    written = dest.read_text(encoding="utf-8")
    assert "\\" not in written


def test_install_hooks_includes_profile_argument(tmp_path, monkeypatch):
    uam_root = _make_uam_hooks(
        tmp_path,
        "claude-code",
        '{"command": "uv run --directory \\"<UAM_PROJECT_DIR>\\" python -m uam.hooks.handler --client claude-code<UAM_PROFILE_ARGS>"}',
    )
    target = _target(tmp_path)
    monkeypatch.setattr("uam.cli.project_root", lambda: uam_root)

    result = runner.invoke(
        app,
        ["install-hooks", "--client", "claude-code", "--target-dir", str(target), "--profile", "focus"],
    )

    assert result.exit_code == 0, result.output
    written = (target / ".claude" / "settings.json").read_text(encoding="utf-8")
    assert "--profile focus" in written


def test_profiles_command_lists_implicit_default(tmp_path, monkeypatch):
    monkeypatch.setattr("uam.profiles.settings.profiles_path", tmp_path / "missing.json")

    result = runner.invoke(app, ["profiles"])

    assert result.exit_code == 0, result.output
    assert '"default_profile": "default"' in result.output


def test_save_profile_and_set_default_commands(tmp_path, monkeypatch):
    registry_path = tmp_path / "uam-profiles.json"
    monkeypatch.setattr("uam.profiles.settings.profiles_path", registry_path)

    save_result = runner.invoke(
        app,
        ["save-profile", "focus", "--memory-prefix", "profiles/focus", "--description", "Focused context"],
    )
    set_result = runner.invoke(app, ["set-default-profile", "focus"])

    assert save_result.exit_code == 0, save_result.output
    assert set_result.exit_code == 0, set_result.output
    assert '"name":"focus"' in set_result.output.replace(" ", "")
