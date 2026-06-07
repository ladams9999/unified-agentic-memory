from __future__ import annotations

"""
Injection contract emitted by this repository:

- SessionStart returns {"system": "..."} for Claude Code, Codex, and Copilot.
- UserPromptSubmit returns {"userPrompt": "..."} for Claude Code, Codex, and Copilot.

The hook config templates in hooks/ wrap harness-specific hook registration around this stable
stdout contract. If a harness needs a different outer shape later, adapt the template, not the
core retrieval logic.
"""

from ..memories import list_memories
from ..models import SearchResult
from ..profiles import resolve_profile
from ..search import hybrid_search


def _render_results(results: list[SearchResult]) -> str:
    return "\n\n".join(f"- {result.title}\n{result.content}" for result in results)


def session_start_payload(client: str, profile_name: str | None = None) -> dict[str, str]:
    profile = resolve_profile(profile_name)
    memories = list_memories(profile.memory_prefix)
    content = "\n\n".join(f"- {memory.path}\n{memory.content}" for memory in memories)
    return {"system": content or "No stored profile memories."}


def user_prompt_payload(client: str, query: str, limit: int = 5, profile_name: str | None = None) -> dict[str, str]:
    resolve_profile(profile_name)
    results = hybrid_search(query, scope="all", limit=limit)
    return {"userPrompt": _render_results(results) or "No relevant memories found."}
