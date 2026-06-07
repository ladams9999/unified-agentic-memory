from __future__ import annotations

import json

import pytest

from uam import profiles


def test_resolve_profile_uses_implicit_default_when_registry_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(profiles.settings, "profiles_path", tmp_path / "missing.json")
    monkeypatch.setattr(profiles.settings, "default_profile", "default")

    profile = profiles.resolve_profile()

    assert profile.name == "default"
    assert profile.memory_prefix == "profiles/"
    assert profile.source == "implicit"


def test_upsert_profile_persists_registry(tmp_path, monkeypatch):
    registry_path = tmp_path / "uam-profiles.json"
    monkeypatch.setattr(profiles.settings, "profiles_path", registry_path)

    profile = profiles.upsert_profile("focus", memory_prefix="profiles/focus", description="Focused context")

    assert profile.name == "focus"
    assert profile.memory_prefix == "profiles/focus/"
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    assert payload["default_profile"] == "focus"
    assert payload["profiles"]["focus"]["memory_prefix"] == "profiles/focus/"


def test_set_default_profile_requires_known_profile(tmp_path, monkeypatch):
    registry_path = tmp_path / "uam-profiles.json"
    monkeypatch.setattr(profiles.settings, "profiles_path", registry_path)
    profiles.upsert_profile("focus", memory_prefix="profiles/focus")

    with pytest.raises(ValueError, match="Unknown profile"):
        profiles.set_default_profile("missing")


def test_resolve_profile_uses_registry_default(tmp_path, monkeypatch):
    registry_path = tmp_path / "uam-profiles.json"
    monkeypatch.setattr(profiles.settings, "profiles_path", registry_path)
    profiles.upsert_profile("focus", memory_prefix="profiles/focus")
    profiles.upsert_profile("review", memory_prefix="profiles/review")
    profiles.set_default_profile("review")

    profile = profiles.resolve_profile()

    assert profile.name == "review"
    assert profile.memory_prefix == "profiles/review/"
