from __future__ import annotations

import json
import subprocess
from pathlib import Path

import typer

from .db import apply_migrations, close_pool, get_connection, project_root
from .dream import run_dream
from .events import list_session_summaries
from .memories import delete_memory, get_memory, list_memories, upsert_memory
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
    typer.echo(json.dumps({"applied": applied}, indent=2))


@app.command()
def store(path: str, content: str, frontmatter: str = "{}") -> None:
    memory = upsert_memory(path, json.loads(frontmatter), content)
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


def main() -> None:
    try:
        app()
    finally:
        close_pool()


if __name__ == "__main__":
    main()
