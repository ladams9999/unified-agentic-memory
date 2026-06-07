from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from .config import settings


def _normalize_memory_prefix(value: str) -> str:
    normalized = value.strip().strip("/")
    return f"{normalized}/" if normalized else "profiles/"


class ProfileConfig(BaseModel):
    memory_prefix: str = "profiles/"
    description: str | None = None

    def model_post_init(self, __context: object) -> None:
        self.memory_prefix = _normalize_memory_prefix(self.memory_prefix)


class ProfileRegistry(BaseModel):
    default_profile: str | None = None
    profiles: dict[str, ProfileConfig] = Field(default_factory=dict)


class RuntimeProfile(BaseModel):
    name: str
    memory_prefix: str = "profiles/"
    description: str | None = None
    source: str = "implicit"


def profiles_path(path: Path | None = None) -> Path:
    return path or settings.profiles_path


def load_profile_registry(path: Path | None = None) -> ProfileRegistry:
    target = profiles_path(path)
    if not target.exists():
        return ProfileRegistry()
    payload = json.loads(target.read_text(encoding="utf-8"))
    return ProfileRegistry.model_validate(payload)


def save_profile_registry(registry: ProfileRegistry, path: Path | None = None) -> Path:
    target = profiles_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(registry.model_dump(mode="json"), indent=2) + "\n", encoding="utf-8")
    return target


def _implicit_profile_name() -> str:
    return settings.default_profile or "default"


def implicit_profile(name: str | None = None) -> RuntimeProfile:
    resolved_name = name or _implicit_profile_name()
    return RuntimeProfile(name=resolved_name, memory_prefix="profiles/", source="implicit")


def list_runtime_profiles(path: Path | None = None) -> tuple[str, list[RuntimeProfile]]:
    registry = load_profile_registry(path)
    default_name = registry.default_profile or settings.default_profile or "default"
    if not registry.profiles:
        return default_name, [implicit_profile(default_name)]
    profiles = [
        RuntimeProfile(
            name=name,
            memory_prefix=config.memory_prefix,
            description=config.description,
            source="registry",
        )
        for name, config in sorted(registry.profiles.items())
    ]
    return default_name, profiles


def resolve_profile(requested_name: str | None = None, path: Path | None = None) -> RuntimeProfile:
    registry = load_profile_registry(path)
    active_name = requested_name or settings.active_profile or registry.default_profile or settings.default_profile or "default"
    if active_name in registry.profiles:
        config = registry.profiles[active_name]
        return RuntimeProfile(
            name=active_name,
            memory_prefix=config.memory_prefix,
            description=config.description,
            source="registry",
        )
    if not registry.profiles and active_name == (settings.default_profile or "default"):
        return implicit_profile(active_name)
    if not registry.profiles and active_name == "default":
        return implicit_profile(active_name)
    raise ValueError(f"Unknown profile '{active_name}'")


def upsert_profile(name: str, *, memory_prefix: str, description: str | None = None, path: Path | None = None) -> RuntimeProfile:
    registry = load_profile_registry(path)
    registry.profiles[name] = ProfileConfig(memory_prefix=memory_prefix, description=description)
    if registry.default_profile is None:
        registry.default_profile = name
    save_profile_registry(registry, path)
    return resolve_profile(name, path)


def set_default_profile(name: str, path: Path | None = None) -> RuntimeProfile:
    registry = load_profile_registry(path)
    if registry.profiles:
        if name not in registry.profiles:
            raise ValueError(f"Unknown profile '{name}'")
        registry.default_profile = name
        save_profile_registry(registry, path)
        return resolve_profile(name, path)
    if name not in {"default", settings.default_profile or "default"}:
        raise ValueError(f"Unknown profile '{name}'")
    settings.default_profile = name
    return implicit_profile(name)
