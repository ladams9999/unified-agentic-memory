from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any

from .db import get_connection
from .embeddings import EmbeddingProvider
from .llm import LLMProvider, OllamaLLMProvider
from .memories import list_memories, upsert_memory
from .models import DreamRun, Memory

DREAM_OUTPUT_FORMAT = """
Output one or more fenced memory blocks in the exact format:

```memory semantic/path.md
---
title: Example
---
Body text
```

Each block path must be unique. Merge with existing knowledge by overwriting the full file content.
""".strip()

MEMORY_BLOCK_PATTERN = re.compile(
    r"```memory\s+(?P<path>[^\n]+)\n(?P<body>.*?)```",
    re.DOTALL,
)


def build_dream_prompt(events: list[dict[str, Any]], memories: list[Memory]) -> str:
    rendered_events = "\n".join(
        f"- [{event['occurred_at']}] {event['event_name']}: {event['content']}"
        for event in events
    )
    rendered_memories = "\n\n".join(
        f"Path: {memory.path}\nContent:\n{memory.content}" for memory in memories
    )
    return (
        "Update the durable memory set from the recent event stream.\n\n"
        f"Recent events:\n{rendered_events or '- none'}\n\n"
        f"Current memories:\n{rendered_memories or '- none'}\n\n"
        f"{DREAM_OUTPUT_FORMAT}"
    )


def parse_memory_blocks(output: str) -> list[tuple[str, dict[str, Any], str]]:
    blocks: list[tuple[str, dict[str, Any], str]] = []
    for match in MEMORY_BLOCK_PATTERN.finditer(output):
        path = match.group("path").strip()
        body = match.group("body").strip()
        frontmatter: dict[str, Any] = {}
        content = body
        if body.startswith("---\n"):
            _, rest = body.split("---\n", 1)
            yaml_block, content = rest.split("\n---\n", 1)
            for line in yaml_block.splitlines():
                if ":" not in line:
                    continue
                key, value = line.split(":", 1)
                frontmatter[key.strip()] = value.strip()
        blocks.append((path, frontmatter, content.strip()))
    return blocks


def run_dream(
    *,
    conn: Any | None = None,
    llm: LLMProvider | None = None,
    embedder: EmbeddingProvider | None = None,
    dry_run: bool = False,
) -> DreamRun:
    started_at = datetime.now(timezone.utc)
    dream_id = uuid.uuid7()
    with get_connection(conn) as active:
        watermark_row = active.execute(
            "SELECT MAX(watermark) FROM uam.dream_runs WHERE watermark IS NOT NULL"
        ).fetchone()
        watermark = watermark_row[0] if watermark_row else None
        if watermark is None:
            rows = active.execute(
                """
                SELECT id, event_name, occurred_at, COALESCE(user_prompt, raw_payload::text)
                FROM uam.events
                ORDER BY occurred_at ASC
                """
            ).fetchall()
        else:
            rows = active.execute(
                """
                SELECT id, event_name, occurred_at, COALESCE(user_prompt, raw_payload::text)
                FROM uam.events
                WHERE occurred_at > %s
                ORDER BY occurred_at ASC
                """,
                (watermark,),
            ).fetchall()
        events = [
            {"id": row[0], "event_name": row[1], "occurred_at": row[2], "content": row[3]}
            for row in rows
        ]
        current_memories = list_memories(conn=active)
        provider = llm or OllamaLLMProvider()
        prompt = build_dream_prompt(events, current_memories)
        response = provider.generate(prompt, system="You maintain concise durable workspace memories.")
        blocks = parse_memory_blocks(response)

        updated = 0
        if not dry_run:
            for path, frontmatter, content in blocks:
                upsert_memory(path, frontmatter, content, conn=active, embedder=embedder)
                updated += 1
            active.execute("TRUNCATE uam.search_cache")

        new_watermark = events[-1]["occurred_at"] if events else watermark
        completed_at = datetime.now(timezone.utc)
        active.execute(
            """
            INSERT INTO uam.dream_runs (
                id, started_at, completed_at, events_processed, memories_updated, watermark
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (dream_id, started_at, completed_at, len(events), updated, new_watermark),
        )
        if conn is None:
            active.commit()
    return DreamRun(
        id=dream_id,
        started_at=started_at,
        completed_at=completed_at,
        events_processed=len(events),
        memories_updated=updated,
        watermark=new_watermark,
    )
