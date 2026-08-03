"""Red-team sandbox evaluation tests."""

from __future__ import annotations

from pathlib import Path

from evals.red_team.sandbox_escape import run


def test_red_team_all_attacks_blocked(tmp_path: Path) -> None:
    """Verify all 10 red-team attacks are blocked or timed out.

    Target from spec: pass_rate >= 0.8 (at least 80% blocked)
    """
    result_path = tmp_path / "result.json"
    result = run(str(result_path))

    # Verify all attacks were executed
    assert result["n_total"] == 10, f"Expected 10 attacks, got {result['n_total']}"

    # Verify JSON was written
    assert result_path.exists(), f"Result file not written to {result_path}"

    # Verify pass rate meets target
    assert result["pass_rate"] >= 0.8, (
        f"Pass rate {result['pass_rate']:.1%} < 80% target. "
        f"Blocked: {result['n_blocked']}/10. "
        f"Failures: {[a for a in result['per_attack'] if not a['blocked']]}"
    )

    # Verify at least 8 attacks blocked
    assert result["n_blocked"] >= 8, (
        f"Expected >= 8 attacks blocked, got {result['n_blocked']}"
    )

    # Verify all attacks have evidence
    for attack in result["per_attack"]:
        assert "evidence" in attack, f"Attack {attack['id']} missing evidence"
        assert len(attack["evidence"]) > 0, f"Attack {attack['id']} has empty evidence"
