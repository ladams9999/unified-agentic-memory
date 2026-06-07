from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from .uuids import uuid7


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class HookEvent(BaseModel):
    id: UUID | None = None
    session_id: UUID | None = None
    profile_name: str | None = None
    client: str
    agent_name: str | None = None
    model_name: str | None = None
    event_name: str
    tool_name: str | None = None
    tool_input: dict[str, Any] | None = None
    user_prompt: str | None = None
    cwd: str | None = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)
    payload_schema_version: str = "1"
    occurred_at: datetime = Field(default_factory=utc_now)

    def with_identifiers(self) -> "HookEvent":
        return self.model_copy(
            update={
                "id": self.id or uuid7(),
                "session_id": self.session_id or uuid7(),
            }
        )

    def embedding_text(self, limit: int = 2000) -> str:
        pieces = [
            self.event_name,
            self.tool_name or "",
            self.user_prompt or "",
            str(self.raw_payload),
        ]
        return " ".join(piece for piece in pieces if piece).strip()[:limit]


class MemoryType(str, Enum):
    fact = "fact"
    learning = "learning"
    idea = "idea"


class Memory(BaseModel):
    id: UUID
    path: str
    frontmatter: dict[str, Any] = Field(default_factory=dict)
    content: str
    memory_type: MemoryType = MemoryType.learning
    embedding: list[float] | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class SearchResult(BaseModel):
    id: str
    source: Literal["event", "memory"]
    path: str | None = None
    title: str
    content: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class DreamRun(BaseModel):
    id: UUID
    started_at: datetime
    completed_at: datetime | None = None
    events_processed: int = 0
    memories_updated: int = 0
    watermark: datetime | None = None


class SessionSummary(BaseModel):
    session_id: UUID
    client: str
    agent_name: str | None = None
    model_name: str | None = None
    started_at: datetime
    event_count: int
