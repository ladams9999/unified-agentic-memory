import json
import uuid
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone
from typing import Any, Literal, Self, get_args, get_origin


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _json_ready(value: Any) -> Any:
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    return value


@dataclass
class ModelBase:
    def model_dump(self, mode: str = "python") -> dict[str, Any]:
        payload = asdict(self)
        return _json_ready(payload) if mode == "json" else payload

    def model_dump_json(self, indent: int | None = None) -> str:
        return json.dumps(self.model_dump(mode="json"), indent=indent)

    def model_copy(self, update: dict[str, Any] | None = None) -> Self:
        data = self.model_dump()
        if update:
            data.update(update)
        return type(self)(**data)

    @classmethod
    def model_validate(cls, payload: dict[str, Any]) -> Self:
        return cls(**payload)


@dataclass
class HookEvent(ModelBase):
    id: uuid.UUID | None = None
    session_id: uuid.UUID | None = None
    client: str = ""
    agent_name: str | None = None
    model_name: str | None = None
    event_name: str = ""
    tool_name: str | None = None
    tool_input: dict[str, Any] | None = None
    user_prompt: str | None = None
    cwd: str | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)
    payload_schema_version: str = "1"
    occurred_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if isinstance(self.id, str):
            self.id = uuid.UUID(self.id)
        if isinstance(self.session_id, str):
            self.session_id = uuid.UUID(self.session_id)
        if isinstance(self.occurred_at, str):
            self.occurred_at = datetime.fromisoformat(self.occurred_at)

    def with_identifiers(self) -> "HookEvent":
        return self.model_copy(
            update={
                "id": self.id or uuid.uuid7(),
                "session_id": self.session_id or uuid.uuid7(),
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


@dataclass
class Memory(ModelBase):
    id: uuid.UUID
    path: str
    frontmatter: dict[str, Any] = field(default_factory=dict)
    content: str = ""
    embedding: list[float] | None = None
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if isinstance(self.id, str):
            self.id = uuid.UUID(self.id)
        if isinstance(self.created_at, str):
            self.created_at = datetime.fromisoformat(self.created_at)
        if isinstance(self.updated_at, str):
            self.updated_at = datetime.fromisoformat(self.updated_at)


@dataclass
class SearchResult(ModelBase):
    id: str
    source: Literal["event", "memory"]
    path: str | None = None
    title: str = ""
    content: str = ""
    score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DreamRun(ModelBase):
    id: uuid.UUID
    started_at: datetime
    completed_at: datetime | None = None
    events_processed: int = 0
    memories_updated: int = 0
    watermark: datetime | None = None

    def __post_init__(self) -> None:
        if isinstance(self.id, str):
            self.id = uuid.UUID(self.id)
        if isinstance(self.started_at, str):
            self.started_at = datetime.fromisoformat(self.started_at)
        if isinstance(self.completed_at, str):
            self.completed_at = datetime.fromisoformat(self.completed_at)
        if isinstance(self.watermark, str):
            self.watermark = datetime.fromisoformat(self.watermark)


@dataclass
class SessionSummary(ModelBase):
    session_id: uuid.UUID
    client: str
    agent_name: str | None = None
    model_name: str | None = None
    started_at: datetime = field(default_factory=utc_now)
    event_count: int = 0

    def __post_init__(self) -> None:
        if isinstance(self.session_id, str):
            self.session_id = uuid.UUID(self.session_id)
        if isinstance(self.started_at, str):
            self.started_at = datetime.fromisoformat(self.started_at)
