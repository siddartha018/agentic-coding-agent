from __future__ import annotations

from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    task_id: str
    workdir: str
    issue: str
    scratchpad: str
    messages: Annotated[list, add_messages]
    diff: str | None
    tests_passed: bool | None
    iterations: int


def new_state(task_id: str, workdir: str, issue: str) -> AgentState:
    return AgentState(
        task_id=task_id,
        workdir=workdir,
        issue=issue,
        scratchpad="",
        messages=[],
        diff=None,
        tests_passed=None,
        iterations=0,
    )
