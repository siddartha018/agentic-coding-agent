from __future__ import annotations

from ..tools.search_code import search_code
from ..llm import get_llm
from ..obs import observed
from ..state import AgentState


@observed(name="node.plan", as_type="agent", capture_input=False)
def plan(
    state: AgentState,
    *,
    llm=None,
    search_fn=None,
) -> dict:
    """Build a planning scratchpad by searching code and prompting the LLM.

    Args:
        state: AgentState with task_id and issue
        llm: LLM instance (default: get_llm())
        search_fn: Search function (default: search_code)

    Returns:
        Dict with key "scratchpad" containing the plan
    """
    llm = llm or get_llm()
    search_fn = search_fn or search_code

    task_id = state["task_id"]
    issue = state["issue"]

    # Search for relevant code snippets
    snippets = search_fn(task_id, issue, k=6)

    # Format snippets for display
    snippet_text = ""
    if snippets:
        snippet_text = "## Relevant Code Snippets\n\n"
        for i, snippet in enumerate(snippets, 1):
            path = snippet.get("path", "unknown")
            symbol = snippet.get("symbol", "")
            start_line = snippet.get("start_line", 0)
            end_line = snippet.get("end_line", 0)
            text = snippet.get("text", "")
            snippet_text += f"### Snippet {i}: {path}:{symbol} (lines {start_line}-{end_line})\n"
            snippet_text += f"```python\n{text}\n```\n\n"

    # Build prompt
    prompt_text = f"""# Issue
{issue}

{snippet_text}
# Plan

Think step-by-step how to fix this issue. Write a brief scratchpad of your approach."""

    # Call LLM
    messages = [{"role": "user", "content": prompt_text}]
    result = llm.chat(messages, model="primary")

    return {"scratchpad": result.content}
