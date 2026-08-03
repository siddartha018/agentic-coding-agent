import pytest
from unittest.mock import Mock, patch

from coding_agent.state import new_state
from coding_agent.nodes.plan import plan


def test_plan_builds_scratchpad_with_snippets(monkeypatch):
    """Test that plan builds a scratchpad containing issue + snippets."""
    # Create initial state
    state = new_state("test-task", "/tmp/workdir", "Fix the off-by-one error")

    # Mock search_code to return some snippets
    mock_snippets = [
        {
            "path": "calc.py",
            "symbol": "add",
            "start_line": 1,
            "end_line": 5,
            "text": "def add(a, b):\n    return a + b + 1  # bug here",
            "score": 0.95,
        },
        {
            "path": "test_calc.py",
            "symbol": "test_add",
            "start_line": 10,
            "end_line": 12,
            "text": "def test_add():\n    assert add(1, 2) == 3",
            "score": 0.80,
        },
    ]

    def mock_search_fn(task_id, query, k=6):
        assert task_id == "test-task"
        assert query == "Fix the off-by-one error"
        assert k == 6
        return mock_snippets

    # Mock LLM
    mock_llm = Mock()
    mock_result = Mock()
    mock_result.content = "1. Check the add function for off-by-one logic\n2. Fix the +1 to correct the result"
    mock_llm.chat.return_value = mock_result

    # Call plan
    result = plan(state, llm=mock_llm, search_fn=mock_search_fn)

    # Verify result structure
    assert "scratchpad" in result
    scratchpad = result["scratchpad"]

    # Verify scratchpad contains expected content
    assert "1. Check the add function for off-by-one logic" in scratchpad
    assert "2. Fix the +1 to correct the result" in scratchpad

    # Verify LLM was called with proper format
    mock_llm.chat.assert_called_once()
    call_args = mock_llm.chat.call_args
    messages = call_args[0][0]
    assert len(messages) == 1
    assert messages[0]["role"] == "user"
    assert "Fix the off-by-one error" in messages[0]["content"]
    assert "calc.py" in messages[0]["content"]
    assert "test_calc.py" in messages[0]["content"]


def test_plan_empty_collection_still_works(monkeypatch):
    """Test that plan works when search_code returns no snippets."""
    state = new_state("test-task", "/tmp/workdir", "Fix something")

    # Mock search_code to return empty list
    def mock_search_fn(task_id, query, k=6):
        return []

    # Mock LLM
    mock_llm = Mock()
    mock_result = Mock()
    mock_result.content = "No code snippets found. Let's proceed with general reasoning."
    mock_llm.chat.return_value = mock_result

    # Call plan
    result = plan(state, llm=mock_llm, search_fn=mock_search_fn)

    # Verify result
    assert "scratchpad" in result
    assert result["scratchpad"] == "No code snippets found. Let's proceed with general reasoning."

    # Verify LLM was called
    mock_llm.chat.assert_called_once()
    call_args = mock_llm.chat.call_args
    messages = call_args[0][0]
    assert "Fix something" in messages[0]["content"]
