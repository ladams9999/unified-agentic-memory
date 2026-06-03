from __future__ import annotations

import json
import subprocess
from pathlib import Path

import typer

from .db import apply_migrations, close_pool, get_connection, project_root
from .dream import run_dream
from .embeddings import get_embedding_provider
from .events import list_session_summaries
from .llm import get_llm_provider
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


@app.command("check-providers")
def check_providers() -> None:
    """Test the configured embedding and LLM providers. Exits 0 on success, 1 on any failure."""
    all_ok = True

    # Test embedding provider
    try:
        embedder = get_embedding_provider()
        provider_name = type(embedder).__name__
        result = embedder.embed("test")
        typer.echo(f"[OK] {provider_name}.embed() returned {len(result)}-dim vector")
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"[FAIL] embedding provider: {exc}")
        all_ok = False

    # Test LLM provider
    try:
        llm = get_llm_provider()
        provider_name = type(llm).__name__
        response = llm.generate("Say hello.", "You are a test.")
        typer.echo(f"[OK] {provider_name}.generate() => {response[:50]!r}")
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"[FAIL] LLM provider: {exc}")
        all_ok = False

    if not all_ok:
        raise typer.Exit(code=1)


def main() -> None:
    try:
        app()
    finally:
        close_pool()


if __name__ == "__main__":
    main()
