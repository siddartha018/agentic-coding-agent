from coding_agent.state import AgentState, new_state


def test_new_state_defaults():
    s = new_state("t1", "/tmp/w", "fix off-by-one")
    assert s["task_id"] == "t1"
    assert s["workdir"] == "/tmp/w"
    assert s["issue"] == "fix off-by-one"
    assert s["scratchpad"] == ""
    assert s["messages"] == []
    assert s["diff"] is None
    assert s["tests_passed"] is None
    assert s["iterations"] == 0
