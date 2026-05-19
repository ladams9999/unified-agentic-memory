from __future__ import annotations

import uuid
from datetime import datetime, timezone

from uam import graph


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
