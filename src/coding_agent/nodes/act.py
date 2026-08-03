from __future__ import annotations

import sys

from langgraph.prebuilt import create_react_agent

from ..tools.search_code import search_code as search_code_impl
from ..tools.open_file import open_file as open_file_impl
from ..tools.edit_file import edit_file as edit_file_impl
from ..tools.run_shell import run_shell as run_shell_impl
from ..tools.run_tests import run_tests as run_tests_impl
from ..tools.submit import submit as submit_impl
from ..llm import get_llm, get_react_model
from ..obs import observed
from ..state import AgentState


def _make_search_code(task_id: str):
    """Wrapper for search_code that injects task_id."""
    def wrapped(query: str, k: int = 6) -> list[dict]:
        return search_code_impl(task_id, query, k)
    wrapped.__name__ = "search_code"
    wrapped.__doc__ = "Search for relevant code snippets in the repository."
    return wrapped


def _make_open_file(workdir: str):
    """Wrapper for open_file that injects workdir."""
    def wrapped(path: str, start: int | None = None, end: int | None = None) -> str:
        return open_file_impl(workdir, path, start, end)
    wrapped.__name__ = "open_file"
    wrapped.__doc__ = "Open and read a file within the workdir."
    return wrapped


def _make_edit_file(workdir: str):
    """Wrapper for edit_file that injects workdir."""
    def wrapped(path: str, old: str, new: str) -> str:
        return edit_file_impl(workdir, path, old, new)
    wrapped.__name__ = "edit_file"
    wrapped.__doc__ = "Replace a unique occurrence of old with new in a file."
    return wrapped


def _make_run_shell(workdir: str):
    """Wrapper for run_shell that injects workdir."""
    def wrapped(cmd: str, timeout: int = 30) -> dict:
        return run_shell_impl(workdir, cmd, timeout)
    wrapped.__name__ = "run_shell"
    wrapped.__doc__ = "Run a shell command string within the sandboxed workdir. Pass a single shell command string (e.g., 'ls -la' or 'pytest tests/')."
    return wrapped


def _make_run_tests(workdir: str):
    """Wrapper for run_tests that injects workdir."""
    def wrapped(target: str | None = None) -> dict:
        return run_tests_impl(workdir, target)
    wrapped.__name__ = "run_tests"
    wrapped.__doc__ = "Run pytest tests within the sandboxed workdir."
    return wrapped


def _make_submit(workdir: str):
    """Wrapper for submit that injects workdir."""
    def wrapped() -> str:
        return submit_impl(workdir)
    wrapped.__name__ = "submit"
    wrapped.__doc__ = "Get a unified diff of changes made in the workdir."
    return wrapped


@observed(name="node.act", as_type="agent", capture_input=False)
def run_act(
    state: AgentState,
    *,
    llm=None,
) -> dict:
    """Run a ReAct loop with tools bound to the current state.

    Args:
        state: AgentState with task_id, workdir, issue, and scratchpad
        llm: LLM instance (default: get_llm())

    Returns:
        Dict with keys: messages, diff, iterations
    """
    llm = llm or get_llm()

    task_id = state["task_id"]
    workdir = state["workdir"]
    issue = state["issue"]
    scratchpad = state["scratchpad"]

    # Create wrapped tools
    tools = [
        _make_search_code(task_id),
        _make_open_file(workdir),
        _make_edit_file(workdir),
        _make_run_shell(workdir),
        _make_run_tests(workdir),
        _make_submit(workdir),
    ]

    # Build system prompt
    system_prompt = f"""You are a coding assistant. Use the tools to implement the fix described below.

Issue: {issue}

Previous plan:
{scratchpad}

Use the tools to:
1. Search for relevant code
2. Open and understand files
3. Make edits to fix the issue
4. Run tests to verify the fix
5. Submit your final changes"""

    # Create ReAct agent with proper BaseChatModel
    react_model = get_react_model()
    agent = create_react_agent(
        model=react_model,
        tools=tools,
        prompt=system_prompt,
    )

    # Build initial messages
    initial_messages = [
        {"role": "user", "content": f"Fix the issue: {issue}"}
    ]

    # Invoke agent
    agent_state = {
        "messages": initial_messages,
    }

    try:
        result = agent.invoke(agent_state)
        agent_messages = result.get("messages", [])
    except Exception as e:
        # Log the exception and surface it in the state update
        print(f"ERROR in run_act: {type(e).__name__}: {e}", file=sys.stderr)
        return {
            "messages": initial_messages,
            "diff": "",
            "iterations": state["iterations"] + 1,
            "error": f"{type(e).__name__}: {str(e)}",
        }

    # Extract diff from final messages
    diff = ""
    try:
        # Try to find diff in messages or run submit
        diff_result = submit_impl(workdir)
        diff = diff_result if diff_result else ""
    except Exception:
        pass

    return {
        "messages": agent_messages,
        "diff": diff,
        "iterations": state["iterations"] + 1,
    }
