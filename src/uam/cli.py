from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Annotated

import typer

from .db import apply_migrations, close_pool, get_connection, project_root
from .dream import run_dream
from .events import list_session_summaries
from .memories import confirm_idea, delete_memory, get_memory, list_memories, upsert_memory
from .models import MemoryType
from .projection import replay_relational_memories
from .search import hybrid_search

app = typer.Typer(help="Unified agentic memory CLI")


def _stack_dir() -> Path:
    return project_root() / "db_stack"


def _ensure_db_stack_running() -> None:
    stack_dir = _stack_dir()
    status = subprocess.run(
        ["docker", "compose", "ps", "-q", "db"],
        cwd=stack_dir,
        check=False,
        capture_output=True,
        text=True,
    )
    if status.stdout.strip():
        return
    subprocess.run(["docker", "compose", "up", "-d", "db"], cwd=stack_dir, check=True)


@app.command()
def migrate() -> None:
    with get_connection() as conn:
        applied = apply_migrations(conn)
        conn.commit()
    with get_connection() as conn:
        memories_projected = replay_relational_memories(conn)
        conn.commit()
    typer.echo(json.dumps({"applied": applied, "memories_projected": memories_projected}, indent=2))


@app.command()
def store(
    path: str,
    content: str,
    frontmatter: str = "{}",
    memory_type: str = "learning",
) -> None:
    memory = upsert_memory(path, json.loads(frontmatter), content, memory_type=MemoryType(memory_type))
    typer.echo(memory.model_dump_json(indent=2))


@app.command("get")
def get_command(path: str) -> None:
    memory = get_memory(path)
    if memory is None:
        raise typer.Exit(code=1)
    typer.echo(memory.model_dump_json(indent=2))


@app.command("delete")
def delete_command(path: str) -> None:
    typer.echo(json.dumps({"deleted": delete_memory(path)}))


@app.command("list")
def list_command(prefix: str = "") -> None:
    typer.echo(json.dumps([memory.model_dump(mode="json") for memory in list_memories(prefix or None)], indent=2))


@app.command("confirm-idea")
def confirm_idea_command(path: str) -> None:
    typer.echo(confirm_idea(path).model_dump_json(indent=2))


@app.command()
def sessions(limit: int = 20) -> None:
    typer.echo(json.dumps(list_session_summaries(limit=limit), indent=2))


@app.command()
def search(query: str, scope: str = "all", limit: int = 5) -> None:
    typer.echo(
        json.dumps(
            [result.model_dump(mode="json") for result in hybrid_search(query, scope, limit)],
            indent=2,
        )
    )


@app.command()
def dream(dry_run: bool = False) -> None:
    _ensure_db_stack_running()
    typer.echo(run_dream(dry_run=dry_run).model_dump_json(indent=2))


# Maps each client to:
#   template_path  — relative path inside hooks/<client>/
#   dest_path      — where the file is written inside --target-dir
_HOOK_INSTALL_MAP: dict[str, dict[str, str]] = {
    "copilot": {
        "template": "hooks/copilot/hooks.json",
        "dest": ".github/hooks/uam-memory.json",
    },
    "claude-code": {
        "template": "hooks/claude-code/settings.json",
        "dest": ".claude/settings.json",
    },
    "codex": {
        "template": "hooks/codex/hooks.json",
        "dest": ".codex/hooks.json",
    },
}


@app.command("install-hooks")
def install_hooks(
    client: Annotated[
        str,
        typer.Option(
            "--client",
            help="Harness to install hooks for: copilot, claude-code, or codex.",
        ),
    ],
    target_dir: Annotated[
        Path,
        typer.Option(
            "--target-dir",
            help="Root of the project where hooks should be installed.",
            exists=True,
            file_okay=False,
            dir_okay=True,
            resolve_path=True,
        ),
    ],
) -> None:
    """Install UAM hook configuration into a target project directory.

    Reads the template from hooks/<client>/ inside the UAM repository,
    substitutes the UAM project root for the <UAM_PROJECT_DIR> placeholder,
    and writes the result to the correct location inside --target-dir.

    The command is idempotent: if the destination file already exists and its
    content matches what would be written, it reports 'already up to date' and
    exits without modifying the file.  If the content differs it warns the user
    and exits without overwriting, so that manual merges (e.g. for
    .claude/settings.json) are never silently lost.
    """
    if client not in _HOOK_INSTALL_MAP:
        typer.echo(
            f"Unknown client '{client}'. Choose from: {', '.join(_HOOK_INSTALL_MAP)}",
            err=True,
        )
        raise typer.Exit(code=1)

    spec = _HOOK_INSTALL_MAP[client]
    uam_root = project_root()
    template_path = uam_root / spec["template"]

    if not template_path.exists():
        typer.echo(f"Template not found: {template_path}", err=True)
        raise typer.Exit(code=1)

    raw = template_path.read_text(encoding="utf-8")
    # Normalise the UAM root to forward slashes so the substituted path is
    # portable on all platforms (the uv --directory flag accepts both on
    # Windows, and forward slashes are required on macOS/Linux).
    uam_root_str = uam_root.as_posix()
    content = raw.replace("<UAM_PROJECT_DIR>", uam_root_str)

    dest = target_dir / spec["dest"]

    if dest.exists():
        existing = dest.read_text(encoding="utf-8")
        if existing == content:
            typer.echo(f"Already up to date: {dest}")
            return
        typer.echo(
            f"WARNING: {dest} already exists with different content.\n"
            "Refusing to overwrite automatically to avoid losing manual edits.\n"
            f"Review the template at {template_path} and merge changes by hand.",
            err=True,
        )
        raise typer.Exit(code=1)

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(content, encoding="utf-8")
    typer.echo(f"Installed: {dest}")


def main() -> None:
    try:
        app()
    finally:
        close_pool()


if __name__ == "__main__":
    main()
