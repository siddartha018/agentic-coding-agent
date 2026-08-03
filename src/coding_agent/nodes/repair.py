from __future__ import annotations

from ..llm import get_llm
from ..obs import observed
from ..state import AgentState


@observed(name="node.repair", as_type="agent", capture_input=False)
def repair(
    state: AgentState,
    *,
    llm=None,
) -> dict:
    """LLM reads the scratchpad and last test failure, returns updated plan.

    Args:
        state: AgentState with scratchpad, messages, and diff
        llm: LLM instance (default: get_llm())

    Returns:
        Dict with key "scratchpad" containing the updated plan
    """
    llm = llm or get_llm()

    scratchpad = state.get("scratchpad", "")
    diff = state.get("diff", "") or ""
    messages = state.get("messages", [])

    # Extract test failure from messages
    test_failure = ""
    if messages:
        # Look for the last few messages to extract test output
        for msg in reversed(messages[-5:]):
            content = msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", "")
            if "FAILED" in content or "ERROR" in content or "passed" in content:
                test_failure += content + "\n"

    # Build repair prompt
    prompt_text = f"""# Original Plan
{scratchpad}

# Test Failure/Output
{test_failure if test_failure else "(No test output captured)"}

# Current Diff
{diff if diff else "(No changes yet)"}

# Revised Plan
Analyze the failure and suggest improvements to fix the issue. Consider:
1. What went wrong?
2. What should be changed?
3. What is the next approach?

Provide a clear, actionable plan for the next iteration."""

    # Call LLM with primary model (more reasoning power for repair)
    messages_for_llm = [{"role": "user", "content": prompt_text}]
    result = llm.chat(messages_for_llm, model="primary")

    return {"scratchpad": result.content}
