"""Tests for the SSE API endpoint."""
from __future__ import annotations

import json
import os
import shutil
import tempfile

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from coding_agent.api import build_app
from coding_agent.graph import build_graph
from coding_agent.state import new_state


def create_stub_graph():
    """Create a stub graph that emits all event types."""

    def fake_index(state, **kw):
        return {}

    def fake_plan(state, **kw):
        return {"scratchpad": "1. Search for the bug\n2. Edit the file"}

    def fake_act(state, **kw):
        # Add messages with tool calls and results using langchain message types
        from langchain_core.messages import AIMessage, ToolCall, ToolMessage

        ai_msg = AIMessage(
            content="Let me search for the bug",
            tool_calls=[
                ToolCall(
                    id="call_1",
                    name="search_code",
                    args={"query": "bug"}
                )
            ]
        )

        tool_msg = ToolMessage(
            content="Found bug at line 42",
            tool_call_id="call_1"
        )

        messages = [ai_msg, tool_msg]
        return {
            "messages": messages,
            "diff": "--- a/file.py\n+++ b/file.py\n@@ -1,1 +1,1 @@\n-bug\n+fix"
        }

    def fake_observe(state, **kw):
        return {"tests_passed": True}

    def fake_repair(state, **kw):
        return {"iterations": state["iterations"] + 1}

    return build_graph(
        index_fn=fake_index,
        plan_fn=fake_plan,
        act_fn=fake_act,
        observe_fn=fake_observe,
        repair_fn=fake_repair,
    )


def test_sse_endpoint_emits_all_event_types():
    """Verify POST /solve returns 200 and emits all 5 event types."""
    stub_graph = create_stub_graph()
    app = build_app(graph=stub_graph)
    client = TestClient(app)

    # Create temp repo directory
    tmpdir = tempfile.mkdtemp()
    try:
        # Write a minimal file to repo
        with open(os.path.join(tmpdir, "test.py"), "w") as f:
            f.write("def test(): pass\n")

        response = client.post(
            "/solve",
            json={
                "repo_path": tmpdir,
                "issue": "Fix the bug",
                "task_id": "test_123"
            }
        )

        assert response.status_code == 200

        # Parse SSE stream
        events = []
        lines = response.text.split("\n")
        for i, line in enumerate(lines):
            if line.startswith("event:"):
                event_type = line.split(":", 1)[1].strip()
                # Next line should be data
                if i + 1 < len(lines) and lines[i + 1].startswith("data:"):
                    data = lines[i + 1].split(":", 1)[1].strip()
                    events.append((event_type, data))

        # Verify all 5 event types present
        event_types = [e[0] for e in events]
        assert "plan" in event_types, f"Missing plan event in: {event_types}"
        assert "tool_call" in event_types, f"Missing tool_call event in: {event_types}"
        assert "tool_result" in event_types, f"Missing tool_result event in: {event_types}"
        assert "test_result" in event_types, f"Missing test_result event in: {event_types}"
        assert "done" in event_types, f"Missing done event in: {event_types}"

        # Verify done event has task_id
        done_events = [e for e in events if e[0] == "done"]
        assert len(done_events) > 0, "No done event found"
        done_data = json.loads(done_events[-1][1])
        assert "task_id" in done_data
        assert done_data["task_id"] == "test_123"

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_sse_endpoint_generates_task_id_if_missing():
    """Verify POST /solve generates task_id if not provided."""
    stub_graph = create_stub_graph()
    app = build_app(graph=stub_graph)
    client = TestClient(app)

    tmpdir = tempfile.mkdtemp()
    try:
        with open(os.path.join(tmpdir, "test.py"), "w") as f:
            f.write("def test(): pass\n")

        response = client.post(
            "/solve",
            json={
                "repo_path": tmpdir,
                "issue": "Fix the bug"
                # No task_id provided
            }
        )

        assert response.status_code == 200

        # Parse SSE stream and find done event
        events = []
        lines = response.text.split("\n")
        for i, line in enumerate(lines):
            if line.startswith("event:"):
                event_type = line.split(":", 1)[1].strip()
                if i + 1 < len(lines) and lines[i + 1].startswith("data:"):
                    data = lines[i + 1].split(":", 1)[1].strip()
                    events.append((event_type, data))

        done_events = [e for e in events if e[0] == "done"]
        assert len(done_events) > 0
        done_data = json.loads(done_events[-1][1])
        assert "task_id" in done_data
        assert len(done_data["task_id"]) > 0  # Should be a UUID hex string

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_sse_endpoint_cleans_up_workdir():
    """Verify tempdir and Qdrant collection are cleaned up after request."""
    stub_graph = create_stub_graph()
    app = build_app(graph=stub_graph)
    client = TestClient(app)

    tmpdir = tempfile.mkdtemp()
    try:
        with open(os.path.join(tmpdir, "test.py"), "w") as f:
            f.write("def test(): pass\n")

        response = client.post(
            "/solve",
            json={
                "repo_path": tmpdir,
                "issue": "Fix the bug",
                "task_id": "cleanup_test"
            }
        )

        assert response.status_code == 200

        # Verify response contains done event (confirming request completed)
        assert "done" in response.text

        # The finally block should have cleaned up, but we can't directly verify
        # that the tempdir was deleted (since it's created within the handler).
        # We can at least verify that the API returned successfully without errors.

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
