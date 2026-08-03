from __future__ import annotations

from ..tools.run_tests import run_tests
from ..obs import observed
from ..state import AgentState


@observed(name="node.observe", as_type="agent", capture_input=False)
def run_observe(
    state: AgentState,
    *,
    run_tests_fn=None,
) -> dict:
    """Run tests and report pass/fail status.

    Args:
        state: AgentState with workdir
        run_tests_fn: Function to run tests (default: run_tests)

    Returns:
        Dict with key "tests_passed" (bool)
    """
    run_tests_fn = run_tests_fn or run_tests

    workdir = state["workdir"]

    # Run tests
    result = run_tests_fn(workdir)

    # Determine pass/fail: all of:
    # - failed == 0
    # - errors == 0
    # - passed > 0
    tests_passed = (
        result.get("failed", 0) == 0
        and result.get("errors", 0) == 0
        and result.get("passed", 0) > 0
    )

    return {"tests_passed": tests_passed}
