from __future__ import annotations

from uam.hooks import injector
from uam.response_cache import get_cached_response, list_cached_responses, upsert_cached_response


def test_session_start_payload_uses_cached_response(tmp_path, monkeypatch):
    state_path = tmp_path / "uam.sqlite3"
    monkeypatch.setattr("uam.response_cache.settings.local_state_path", state_path)
    monkeypatch.setattr("uam.profiles.settings.profiles_path", tmp_path / "profiles.json")
    monkeypatch.setattr(injector, "_session_start_text", lambda profile_name=None: "fresh")

    upsert_cached_response(
        kind="session_start",
        client="claude-code",
        profile_name="default",
        response_text="cached profile memory",
    )

    payload = injector.session_start_payload("claude-code")

    assert payload == {"system": "cached profile memory"}


def test_user_prompt_payload_writes_cache_on_miss(tmp_path, monkeypatch):
    state_path = tmp_path / "uam.sqlite3"
    monkeypatch.setattr("uam.response_cache.settings.local_state_path", state_path)
    monkeypatch.setattr("uam.profiles.settings.profiles_path", tmp_path / "profiles.json")
    monkeypatch.setattr(injector, "_user_prompt_text", lambda query, limit=5, profile_name=None: f"result:{query}")

    payload = injector.user_prompt_payload("claude-code", "where is auth?")

    assert payload == {"userPrompt": "result:where is auth?"}
    assert get_cached_response(
        kind="user_prompt",
        client="claude-code",
        profile_name="default",
        query_text="where is auth?",
    ) == "result:where is auth?"


def test_refresh_cached_responses_updates_existing_entries(tmp_path, monkeypatch):
    state_path = tmp_path / "uam.sqlite3"
    monkeypatch.setattr("uam.response_cache.settings.local_state_path", state_path)
    monkeypatch.setattr("uam.profiles.settings.profiles_path", tmp_path / "profiles.json")
    monkeypatch.setattr(injector, "_session_start_text", lambda profile_name=None: "fresh session")
    monkeypatch.setattr(
        injector,
        "_user_prompt_text",
        lambda query, limit=5, profile_name=None: f"fresh:{query}",
    )

    upsert_cached_response(
        kind="session_start",
        client="claude-code",
        profile_name="default",
        response_text="stale session",
    )
    upsert_cached_response(
        kind="user_prompt",
        client="claude-code",
        profile_name="default",
        query_text="test query",
        response_text="stale query",
    )

    result = injector.refresh_cached_responses()
    cached = {entry.kind: entry for entry in list_cached_responses()}

    assert result == {"refreshed": 2}
    assert cached["session_start"].response_text == "fresh session"
    assert cached["user_prompt"].response_text == "fresh:test query"
