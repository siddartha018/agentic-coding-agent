import pytest
from unittest.mock import Mock

from coding_agent.state import new_state
from coding_agent.nodes.repair import repair


def test_repair_uses_scratchpad_and_diff():
    """Test that repair uses scratchpad and diff context in its prompt."""
    state = new_state("test-task", "/tmp/workdir", "Fix the bug")
    state["scratchpad"] = "Original plan: Check the add function"
    state["diff"] = """--- a/calc.py
+++ b/calc.py
@@ -1,3 +1,3 @@
 def add(a, b):
-    return a + b + 1
+    return a + b
"""
    state["messages"] = [
        {"role": "user", "content": "Fix the bug"},
        {"role": "assistant", "content": "FAILED: test_add"},
    ]

    # Mock LLM
    mock_llm = Mock()
    mock_result = Mock()
    mock_result.content = "Revised plan: The fix looks good but we need to verify all tests pass."
    mock_llm.chat.return_value = mock_result

    # Call repair
    result = repair(state, llm=mock_llm)

    # Verify result
    assert "scratchpad" in result
    assert result["scratchpad"] == "Revised plan: The fix looks good but we need to verify all tests pass."

    # Verify LLM was called with proper context
    mock_llm.chat.assert_called_once()
    call_args = mock_llm.chat.call_args
    messages = call_args[0][0]
    content = messages[0]["content"]

    # Verify scratchpad and diff are in the prompt
    assert "Original plan: Check the add function" in content
    assert "return a + b" in content  # From diff
    assert "test_add" in content  # From messages


def test_repair_handles_no_diff():
    """Test that repair works when diff is empty or None."""
    state = new_state("test-task", "/tmp/workdir", "Fix the bug")
    state["scratchpad"] = "Initial plan to fix the issue"
    state["diff"] = None
    state["messages"] = [
        {"role": "assistant", "content": "ERROR: Something went wrong"},
    ]

    # Mock LLM
    mock_llm = Mock()
    mock_result = Mock()
    mock_result.content = "Let's start over with a different approach."
    mock_llm.chat.return_value = mock_result

    # Call repair
    result = repair(state, llm=mock_llm)

    # Verify result
    assert "scratchpad" in result
    assert result["scratchpad"] == "Let's start over with a different approach."

    # Verify LLM was called
    mock_llm.chat.assert_called_once()
    call_args = mock_llm.chat.call_args
    messages = call_args[0][0]
    content = messages[0]["content"]

    # Verify scratchpad is in the prompt
    assert "Initial plan to fix the issue" in content
    assert "No changes yet" in content  # From empty diff handling
