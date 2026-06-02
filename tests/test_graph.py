from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

from uam import graph
from uam.projection import project_memory, remove_memory_projection, replay_relational_memories


def test_graph_creates_and_orders_events(monkeypatch):
    state = {"sessions": set(), "events": {}, "links": {}, "session_events": {}}

    def fake_run_cypher(conn, query):
        if "MERGE (s:Session" in query:
            session_id = query.split('id: "', 1)[1].split('"', 1)[0]
            state["sessions"].add(session_id)
            return []
        if "MERGE (e:Event" in query:
            event_id = query.rsplit('id: "', 1)[1].split('"', 1)[0]
            occurred_at = query.split('e.occurred_at = "', 1)[1].split('"', 1)[0]
            state["events"][event_id] = {"id": event_id, "occurred_at": occurred_at}
            return []
        if "MERGE (s)-[:HAS_EVENT]->(e)" in query:
            session_id = query.split('id: "', 1)[1].split('"', 1)[0]
            event_id = query.rsplit('id: "', 1)[1].split('"', 1)[0]
            state["session_events"].setdefault(session_id, []).append(event_id)
            return []
        if "MERGE (prev)-[:NEXT_EVENT]->(curr)" in query:
            previous_event_id = query.split('id: "', 1)[1].split('"', 1)[0]
            event_id = query.rsplit('id: "', 1)[1].split('"', 1)[0]
            state["links"][previous_event_id] = event_id
            return []
        if "RETURN e ORDER BY e.occurred_at, e.id" in query:
            session_id = query.split('id: "', 1)[1].split('"', 1)[0]
            ordered = sorted(
                state["session_events"][session_id],
                key=lambda event_id: state["events"][event_id]["occurred_at"],
            )
            return [(f'{{"id":"{event_id}","occurred_at":"{state["events"][event_id]["occurred_at"]}"}}::vertex',) for event_id in ordered]
        raise AssertionError(query)

    monkeypatch.setattr(graph, "_run_cypher", fake_run_cypher)

    session_id = uuid.uuid4()
    first = uuid.uuid4()
    second = uuid.uuid4()
    graph.create_session(object(), session_id, "claude-code")
    graph.create_event(object(), first, session_id, "SessionStart", datetime(2026, 1, 1, tzinfo=timezone.utc))
    graph.link_event(object(), session_id, first)
    graph.create_event(object(), second, session_id, "UserPromptSubmit", datetime(2026, 1, 2, tzinfo=timezone.utc))
    graph.link_event(object(), session_id, second, first)

    events = graph.get_session_events(object(), session_id)
    assert [event["id"] for event in events] == [str(first), str(second)]
    assert state["links"][str(first)] == str(second)


def _make_memory_cypher_state():
    """Return a minimal fake Cypher engine that tracks Directory and Memory nodes."""
    directories: dict[str, dict] = {}
    memories: dict[str, dict] = {}
    child_edges: list[tuple[str, str]] = []
    parent_child_edges: list[tuple[str, str]] = []
    deleted_memories: set[str] = set()
    deleted_dirs: set[str] = set()

    def fake_run_cypher(conn, query):
        nonlocal directories, memories, child_edges

        if "MERGE (parent:Directory" in query and "MERGE (child:Directory" in query:
            parent_path = query.split("parent:Directory {path: ", 1)[1].split("}", 1)[0].strip('"')
            child_path = query.split("child:Directory {path: ", 1)[1].split("}", 1)[0].strip('"')
            directories.setdefault(parent_path, {"path": parent_path})
            directories.setdefault(child_path, {"path": child_path})
            child_edges.append((parent_path, child_path))
            return []

        if "MERGE (d:Directory" in query and "RETURN d" in query:
            path = query.split("path: ", 1)[1].split("}", 1)[0].strip('"')
            directories.setdefault(path, {"path": path})
            return []

        if "MERGE (m:Memory" in query and "SET m.id" in query:
            path = query.split("Memory {path: ", 1)[1].split("}", 1)[0].strip('"')
            mem_id = query.split("m.id = ", 1)[1].split(" ", 1)[0].strip('"')
            memories[path] = {"path": path, "id": mem_id}
            return []

        if "MERGE (parent)-[:CHILD]->(m)" in query:
            parent_path = query.split("parent:Directory {path: ", 1)[1].split("}", 1)[0].strip('"')
            child_path = query.split("m:Memory {path: ", 1)[1].split("}", 1)[0].strip('"')
            parent_child_edges.append((parent_path, child_path))
            return []

        if "DETACH DELETE m" in query:
            path = query.split("Memory {path: ", 1)[1].split("}", 1)[0].strip('"')
            deleted_memories.add(path)
            memories.pop(path, None)
            child_edges[:] = [(p, c) for p, c in child_edges if c != path]
            parent_child_edges[:] = [(p, c) for p, c in parent_child_edges if c != path]
            return []

        if "count(child)" in query:
            seg = query.split("Directory {path: ", 1)[1].split("}", 1)[0].strip('"')
            # Count children still present
            children = [c for p, c in child_edges + parent_child_edges if p == seg and c not in deleted_memories and c not in deleted_dirs]
            return [(f'{{"c":{len(children)}}}::agtype',)]

        if "DETACH DELETE d" in query:
            seg = query.split("Directory {path: ", 1)[1].split("}", 1)[0].strip('"')
            deleted_dirs.add(seg)
            directories.pop(seg, None)
            child_edges[:] = [(p, c) for p, c in child_edges if p != seg and c != seg]
            return []

        raise AssertionError(f"Unexpected query: {query!r}")

    return fake_run_cypher, directories, memories, child_edges, parent_child_edges, deleted_dirs


def test_ensure_path_nodes_creates_directory_hierarchy(monkeypatch):
    fake_run_cypher, directories, _, child_edges, _, _ = _make_memory_cypher_state()
    monkeypatch.setattr(graph, "_run_cypher", fake_run_cypher)

    graph.ensure_path_nodes(object(), "profiles/user/prefs")

    assert "profiles" in directories
    assert "profiles/user" in directories
    # Child edges link each segment to the next
    assert ("profiles", "profiles/user") in child_edges
    assert ("profiles/user", "profiles/user/prefs") in child_edges


def test_upsert_memory_node_creates_node_and_attaches_to_parent(monkeypatch):
    fake_run_cypher, directories, memories, _, parent_child_edges, _ = _make_memory_cypher_state()
    monkeypatch.setattr(graph, "_run_cypher", fake_run_cypher)

    mem_id = uuid.uuid4()
    graph.upsert_memory_node(object(), mem_id, "profiles/user/prefs")

    assert "profiles/user/prefs" in memories
    assert memories["profiles/user/prefs"]["id"] == str(mem_id)
    assert ("profiles/user", "profiles/user/prefs") in parent_child_edges


def test_upsert_memory_node_flat_path(monkeypatch):
    """A single-segment path creates a Memory node with no parent directory."""
    fake_run_cypher, directories, memories, _, parent_child_edges, _ = _make_memory_cypher_state()
    monkeypatch.setattr(graph, "_run_cypher", fake_run_cypher)

    mem_id = uuid.uuid4()
    graph.upsert_memory_node(object(), mem_id, "standalone")

    assert "standalone" in memories
    assert parent_child_edges == []


def test_delete_memory_node_removes_and_prunes_orphans(monkeypatch):
    fake_run_cypher, directories, memories, child_edges, parent_child_edges, deleted_dirs = _make_memory_cypher_state()
    monkeypatch.setattr(graph, "_run_cypher", fake_run_cypher)

    mem_id = uuid.uuid4()
    graph.upsert_memory_node(object(), mem_id, "profiles/tmp/note")
    assert "profiles/tmp/note" in memories

    graph.delete_memory_node(object(), "profiles/tmp/note")

    assert "profiles/tmp/note" not in memories
    # The intermediate directory "profiles/tmp" had only this one child and should be pruned
    assert "profiles/tmp" in deleted_dirs


def test_project_memory_calls_upsert(monkeypatch):
    import uam.projection as projection_mod

    calls = []

    def fake_upsert(conn, memory_id, path):
        calls.append((memory_id, path))

    monkeypatch.setattr(projection_mod, "upsert_memory_node", fake_upsert)

    from uam.models import Memory

    mem = Memory(id=uuid.uuid4(), path="foo/bar", frontmatter={}, content="hello")
    project_memory(object(), mem)

    assert calls == [(mem.id, "foo/bar")]


def test_replay_relational_memories_projects_all(monkeypatch):
    import uam.projection as projection_mod

    projected = []

    def fake_upsert(conn, memory_id, path):
        projected.append(path)

    monkeypatch.setattr(projection_mod, "upsert_memory_node", fake_upsert)

    import uuid as _uuid
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    rows = [
        (_uuid.uuid4(), "a/b", {}, "content1", "learning", None, now, now),
        (_uuid.uuid4(), "c/d", {}, "content2", "learning", None, now, now),
    ]
    fake_conn = MagicMock()
    fake_conn.execute.return_value.fetchall.return_value = rows

    count = replay_relational_memories(fake_conn)

    assert count == 2
    assert projected == ["a/b", "c/d"]
