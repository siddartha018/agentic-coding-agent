from coding_agent.tools.run_tests import _parse_pytest_output


def test_parses_passing_run():
    """Test parsing of a successful pytest run."""
    raw = "..\n\n=== 2 passed in 0.05s ==="
    r = _parse_pytest_output(raw)
    assert r["passed"] == 2
    assert r["failed"] == 0
    assert r["errors"] == 0


def test_parses_failing_run():
    """Test parsing of a pytest run with failures."""
    raw = "F.\n\n=== 1 failed, 1 passed in 0.10s ==="
    r = _parse_pytest_output(raw)
    assert r["passed"] == 1
    assert r["failed"] == 1
    assert r["errors"] == 0


def test_parses_mixed_results():
    """Test parsing of a pytest run with mixed results."""
    raw = "F.E\n\n=== 1 failed, 1 passed, 1 error in 0.15s ==="
    r = _parse_pytest_output(raw)
    assert r["passed"] == 1
    assert r["failed"] == 1
    assert r["errors"] == 1


def test_parses_all_failures():
    """Test parsing of a pytest run with only failures."""
    raw = "FF\n\n=== 2 failed in 0.20s ==="
    r = _parse_pytest_output(raw)
    assert r["passed"] == 0
    assert r["failed"] == 2
    assert r["errors"] == 0


def test_empty_output():
    """Test parsing of empty pytest output."""
    raw = ""
    r = _parse_pytest_output(raw)
    assert r["passed"] == 0
    assert r["failed"] == 0
    assert r["errors"] == 0
    assert r["raw"] == ""


def test_parses_full_pytest_output_with_banner():
    """Test parsing of full pytest output that includes session start banner.

    This ensures we grab the LAST summary block, not the first === line.
    """
    raw = """=== test session starts ===
platform linux -- Python 3.12.3, pytest-7.4.0
collected 2 items

test_calc.py F.

=== 1 failed, 1 passed in 0.10s ==="""
    r = _parse_pytest_output(raw)
    assert r["passed"] == 1
    assert r["failed"] == 1
    assert r["errors"] == 0
