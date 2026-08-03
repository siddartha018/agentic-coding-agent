from __future__ import annotations

import json
import shutil
import tempfile
import uuid
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from . import obs
from .graph import build_graph
from .state import new_state
from .nodes.index import run_index
from .nodes.plan import plan as plan_fn
from .nodes.act import run_act
from .nodes.observe import run_observe
from .nodes.repair import repair as repair_fn


class SolveRequest(BaseModel):
    repo_path: str
    issue: str
    task_id: str | None = None


def _to_jsonable(v: Any) -> Any:
    """Recursively convert dataclass objects and other complex types to JSON-serializable dicts."""
    if hasattr(v, "__dataclass_fields__"):
        # It's a dataclass
        return {f: _to_jsonable(getattr(v, f)) for f in v.__dataclass_fields__}
    if isinstance(v, list):
        return [_to_jsonable(x) for x in v]
    if isinstance(v, dict):
        return {k: _to_jsonable(x) for k, x in v.items()}
    return v


def _extract_tool_calls_and_results(messages: list) -> tuple[list[dict], list[dict]]:
    """Extract tool calls and results from messages.

    Returns: (tool_calls, tool_results) where each is a list of dicts
    """
    tool_calls = []
    tool_results = []

    for msg in messages:
        # Handle langchain message objects
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                tool_calls.append(_to_jsonable(tc))

        # Handle ToolMessage (tool results)
        if hasattr(msg, "__class__") and msg.__class__.__name__ == "ToolMessage":
            tool_results.append(_to_jsonable({
                "type": "tool",
                "tool_use_id": getattr(msg, "tool_call_id", None),
                "content": getattr(msg, "content", "")
            }))

        # Also handle dict format for backward compatibility
        if isinstance(msg, dict):
            # Look for tool_calls in message content
            if "tool_calls" in msg:
                for tc in msg.get("tool_calls", []):
                    tool_calls.append(_to_jsonable(tc))
            # Look for tool_results
            if "type" in msg and msg["type"] == "tool":
                tool_results.append(_to_jsonable(msg))

    return tool_calls, tool_results


def build_app(*, graph=None) -> FastAPI:
    """Factory for FastAPI app with SSE /solve endpoint.

    Args:
        graph: Optional compiled LangGraph. If None, uses build_graph().

    Returns:
        FastAPI app with /solve endpoint.
    """
    app = FastAPI(title="coding-agent")
    the_graph = graph or build_graph(
        index_fn=run_index,
        plan_fn=plan_fn,
        act_fn=run_act,
        observe_fn=run_observe,
        repair_fn=repair_fn,
    )
    obs.init_langfuse()

    @app.post("/solve")
    async def solve(req: SolveRequest):
        task_id = req.task_id or uuid.uuid4().hex
        workdir = tempfile.mkdtemp(prefix=f"coding_agent_{task_id}_")

        async def gen():
            try:
                # Copy repo to workdir
                shutil.copytree(req.repo_path, workdir, dirs_exist_ok=True)

                # Initialize state
                state = new_state(task_id, workdir, req.issue)

                # Track what we've already emitted
                emitted_plan = False
                emitted_tool_calls = set()  # Track by tool name + input hash
                emitted_tool_results = set()  # Track by result hash
                emitted_tests = False

                with obs.trace_context(session_id=task_id, tags=["coding-agent", "api"]):
                    # Stream state updates from graph
                    for update in the_graph.stream(state, stream_mode="values"):
                        # Emit plan event
                        if "scratchpad" in update and update["scratchpad"] and not emitted_plan:
                            emitted_plan = True
                            plan_data = json.dumps({
                                "scratchpad": update["scratchpad"]
                            })
                            yield {"event": "plan", "data": plan_data}

                        # Emit tool_call events from messages
                        if "messages" in update:
                            tool_calls, tool_results = _extract_tool_calls_and_results(update["messages"])

                            # Emit new tool calls
                            for tc in tool_calls:
                                tc_hash = json.dumps(tc, sort_keys=True)
                                if tc_hash not in emitted_tool_calls:
                                    emitted_tool_calls.add(tc_hash)
                                    tool_call_data = json.dumps({"tool_call": tc})
                                    yield {"event": "tool_call", "data": tool_call_data}

                            # Emit new tool results
                            for tr in tool_results:
                                tr_hash = json.dumps(tr, sort_keys=True)
                                if tr_hash not in emitted_tool_results:
                                    emitted_tool_results.add(tr_hash)
                                    tool_result_data = json.dumps({"tool_result": tr})
                                    yield {"event": "tool_result", "data": tool_result_data}

                        # Emit test_result event
                        if "tests_passed" in update and update["tests_passed"] is not None and not emitted_tests:
                            emitted_tests = True
                            test_data = json.dumps({
                                "tests_passed": update["tests_passed"]
                            })
                            yield {"event": "test_result", "data": test_data}

                    # Flush before done event
                    obs.flush()

                    # Emit done event with final result
                    done_data = json.dumps({
                        "task_id": task_id,
                        "diff": update.get("diff", ""),
                        "iterations": update.get("iterations", 0)
                    })
                    yield {"event": "done", "data": done_data}

            finally:
                # Clean up workdir
                shutil.rmtree(workdir, ignore_errors=True)
                # Clean up Qdrant collection
                try:
                    from .indexing.qdrant import delete_task_collection
                    delete_task_collection(task_id)
                except Exception:
                    pass

        return EventSourceResponse(gen())

    return app


app = build_app()
