from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .dream import run_dream
from .events import list_session_summaries
from .memories import confirm_idea, delete_memory, get_memory, list_memories, upsert_memory
from .models import MemoryType
from .search import hybrid_search

mcp = FastMCP("uam-memory")


@mcp.tool()
def uam_search(query: str, scope: str = "all", limit: int = 5) -> list[dict]:
    return [result.model_dump(mode="json") for result in hybrid_search(query, scope, limit)]


@mcp.tool()
def uam_store(
    path: str,
    content: str,
    frontmatter: dict | None = None,
    memory_type: str = "learning",
) -> dict:
    mt = MemoryType(memory_type)
    return upsert_memory(path, frontmatter or {}, content, memory_type=mt).model_dump(mode="json")


@mcp.tool()
def uam_get(path: str) -> dict | None:
    memory = get_memory(path)
    return memory.model_dump(mode="json") if memory else None


@mcp.tool()
def uam_delete(path: str) -> dict:
    return {"deleted": delete_memory(path)}


@mcp.tool()
def uam_list(prefix: str = "") -> list[dict]:
    return [memory.model_dump(mode="json") for memory in list_memories(prefix or None)]


@mcp.tool()
def uam_sessions(limit: int = 20) -> dict:
    return {"sessions": list_session_summaries(limit=limit)}


@mcp.tool()
def uam_confirm_idea(path: str) -> dict:
    return confirm_idea(path).model_dump(mode="json")


@mcp.tool()
def uam_dream(dry_run: bool = False) -> dict:
    return run_dream(dry_run=dry_run).model_dump(mode="json")


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
