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
from ..response_cache import get_cached_response, list_cached_responses, upsert_cached_response
from ..search import hybrid_search


def _render_results(results: list[SearchResult]) -> str:
    return "\n\n".join(f"- {result.title}\n{result.content}" for result in results)


def _session_start_text(profile_name: str | None = None) -> str:
    profile = resolve_profile(profile_name)
    memories = list_memories(profile.memory_prefix)
    return "\n\n".join(f"- {memory.path}\n{memory.content}" for memory in memories) or "No stored profile memories."


def _user_prompt_text(query: str, limit: int = 5, profile_name: str | None = None) -> str:
    resolve_profile(profile_name)
    results = hybrid_search(query, scope="all", limit=limit)
    return _render_results(results) or "No relevant memories found."


def session_start_payload(client: str, profile_name: str | None = None) -> dict[str, str]:
    profile = resolve_profile(profile_name)
    cached = get_cached_response(kind="session_start", client=client, profile_name=profile.name)
    if cached is not None:
        return {"system": cached}
    content = _session_start_text(profile.name)
    upsert_cached_response(kind="session_start", client=client, profile_name=profile.name, response_text=content)
    return {"system": content}


def user_prompt_payload(client: str, query: str, limit: int = 5, profile_name: str | None = None) -> dict[str, str]:
    profile = resolve_profile(profile_name)
    cached = get_cached_response(
        kind="user_prompt",
        client=client,
        profile_name=profile.name,
        query_text=query,
    )
    if cached is not None:
        return {"userPrompt": cached}
    content = _user_prompt_text(query, limit=limit, profile_name=profile.name)
    upsert_cached_response(
        kind="user_prompt",
        client=client,
        profile_name=profile.name,
        query_text=query,
        response_text=content,
    )
    return {"userPrompt": content}


def refresh_cached_responses() -> dict[str, int]:
    refreshed = 0
    for entry in list_cached_responses():
        if entry.kind == "session_start":
            response_text = _session_start_text(entry.profile_name)
        else:
            response_text = _user_prompt_text(entry.query_text or "", profile_name=entry.profile_name)
        upsert_cached_response(
            kind=entry.kind,
            client=entry.client,
            profile_name=entry.profile_name,
            query_text=entry.query_text,
            response_text=response_text,
        )
        refreshed += 1
    return {"refreshed": refreshed}
