from coding_agent.graph import build_graph
from coding_agent.state import new_state


def test_graph_end_to_end_with_fakes():
    def fake_index(state, **kw):
        return {}

    def fake_plan(state, **kw):
        return {"scratchpad": "look at calc.py"}

    def fake_act(state, **kw):
        return {"diff": "--- a/calc.py\n+++ b/calc.py\n+return x+1\n"}

    def fake_observe(state, **kw):
        return {"tests_passed": True}

    def fake_repair(state, **kw):
        return {"iterations": state["iterations"] + 1}

    g = build_graph(
        index_fn=fake_index,
        plan_fn=fake_plan,
        act_fn=fake_act,
        observe_fn=fake_observe,
        repair_fn=fake_repair,
    )
    out = g.invoke(new_state("t1", "/tmp", "fix it"))
    assert out["tests_passed"] is True
    assert out["diff"] is not None
