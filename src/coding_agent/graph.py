from __future__ import annotations

import shutil
import tempfile
import concurrent.futures

from langgraph.graph import END, START, StateGraph

from . import obs
from .state import AgentState, new_state
from .nodes.index import run_index
from .nodes.plan import plan as plan_fn
from .nodes.act import run_act
from .nodes.observe import run_observe
from .nodes.repair import repair as repair_fn
from .config import get_settings


def build_graph(
    *,
    index_fn=None,
    plan_fn=None,
    act_fn=None,
    observe_fn=None,
    repair_fn=None,
):
    """Build a LangGraph state machine with injectable node functions.

    Args:
        index_fn: Function to execute at the index node
        plan_fn: Function to execute at the plan node
        act_fn: Function to execute at the act node
        observe_fn: Function to execute at the observe node
        repair_fn: Function to execute at the repair node

    Returns:
        CompiledGraph: A compiled LangGraph state machine
    """
    index_fn = index_fn or (lambda s, **k: {})
    plan_fn = plan_fn or (lambda s, **k: {})
    act_fn = act_fn or (lambda s, **k: {})
    observe_fn = observe_fn or (lambda s, **k: {})
    repair_fn = repair_fn or (lambda s, **k: {})

    def index_node(state: AgentState) -> dict:
        return index_fn(state)

    def plan_node(state: AgentState) -> dict:
        return plan_fn(state)

    def act_node(state: AgentState) -> dict:
        return act_fn(state)

    def observe_node(state: AgentState) -> dict:
        return observe_fn(state)

    def repair_node(state: AgentState) -> dict:
        return repair_fn(state)

    def route_after_observe(state: AgentState) -> str:
        if state["tests_passed"]:
            return "done"
        if state["iterations"] >= get_settings().coding_agent_max_iterations:
            return "done"
        return "repair"

    g = StateGraph(AgentState)
    g.add_node("index", index_node)
    g.add_node("plan", plan_node)
    g.add_node("act", act_node)
    g.add_node("observe", observe_node)
    g.add_node("repair", repair_node)
    g.add_edge(START, "index")
    g.add_edge("index", "plan")
    g.add_edge("plan", "act")
    g.add_edge("act", "observe")
    g.add_conditional_edges(
        "observe", route_after_observe, {"done": END, "repair": "repair"}
    )
    g.add_edge("repair", "act")
    return g.compile()


def run(repo_path: str, issue: str, task_id: str) -> AgentState:
    """Copy repo → run graph → clean up. Delete Qdrant collection in finally.

    Args:
        repo_path: Path to the repository to copy
        issue: The issue/task description
        task_id: Unique identifier for this task

    Returns:
        AgentState: The final state after graph execution
    """
    obs.init_langfuse()
    settings = get_settings()
    workdir = tempfile.mkdtemp(prefix=f"coding_agent_{task_id}_")
    shutil.copytree(repo_path, workdir, dirs_exist_ok=True)
    try:
        with obs.trace_context(session_id=task_id, tags=["coding-agent"]):
            # Build graph with real node functions
            graph = build_graph(
                index_fn=run_index,
                plan_fn=plan_fn,
                act_fn=run_act,
                observe_fn=run_observe,
                repair_fn=repair_fn,
            )

            # Run with wall-clock timeout
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(graph.invoke, new_state(task_id, workdir, issue))
                try:
                    result = future.result(timeout=settings.coding_agent_task_timeout_sec)
                except concurrent.futures.TimeoutError:
                    # Force a final state on timeout
                    result = {
                        "task_id": task_id,
                        "workdir": workdir,
                        "issue": issue,
                        "scratchpad": "",
                        "messages": [],
                        "diff": None,
                        "tests_passed": False,
                        "iterations": 0,
                        "error": "task_timeout",
                    }
        obs.flush()
        return result
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
        try:
            from .indexing.qdrant import delete_task_collection

            delete_task_collection(task_id)
        except Exception:
            pass
