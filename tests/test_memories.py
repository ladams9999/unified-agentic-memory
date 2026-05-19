from __future__ import annotations

from uam import memories


class StubEmbedder:
    def embed(self, text: str) -> list[float]:
        return [float(len(text))] * 768


def test_memory_crud(fake_memory_conn):
    original = memories.upsert_memory(
        "topics/test.md",
        {"title": "Test"},
        "hello",
        conn=fake_memory_conn,
        embedder=StubEmbedder(),
    )
    assert original.path == "topics/test.md"

    loaded = memories.get_memory("topics/test.md", conn=fake_memory_conn)
    assert loaded is not None
    assert loaded.content == "hello"

    updated = memories.upsert_memory(
        "topics/test.md",
        {"title": "Updated"},
        "hello world",
        conn=fake_memory_conn,
        embedder=StubEmbedder(),
    )
    assert updated.frontmatter["title"] == "Updated"
    assert updated.embedding == [11.0] * 768

    listed = memories.list_memories("topics/", conn=fake_memory_conn)
    assert [memory.path for memory in listed] == ["topics/test.md"]

    assert memories.delete_memory("topics/test.md", conn=fake_memory_conn) is True
    assert memories.get_memory("topics/test.md", conn=fake_memory_conn) is None
