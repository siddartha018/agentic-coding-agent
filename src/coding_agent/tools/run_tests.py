from __future__ import annotations

import re

from ..sandbox.workdir import run_in_sandbox
from ..obs import observed


def _parse_pytest_output(raw: str) -> dict:
    """Parse pytest -q output to extract test counts.

    Expected pytest -q format:
        .F.E
        === 2 passed, 1 failed, 1 error in 0.10s ===

    Returns dict with keys: passed, failed, errors, raw
    """
    passed = 0
    failed = 0
    errors = 0

    # Look for the summary line pattern (grab the LAST match, not the first)
    # Matches patterns like: "2 passed in 0.10s" or "1 failed, 1 passed in 0.10s"
    summary_pattern = r"=+\s*(.*?)\s*=+"
    matches = re.findall(summary_pattern, raw)
    if matches:
        summary_text = matches[-1]  # Take the last match

        # Extract counts from summary
        passed_match = re.search(r"(\d+)\s+passed", summary_text)
        if passed_match:
            passed = int(passed_match.group(1))

        failed_match = re.search(r"(\d+)\s+failed", summary_text)
        if failed_match:
            failed = int(failed_match.group(1))

        error_match = re.search(r"(\d+)\s+error", summary_text)
        if error_match:
            errors = int(error_match.group(1))

    return {"passed": passed, "failed": failed, "errors": errors, "raw": raw}


@observed(name="tool.run_tests", as_type="tool")
def run_tests(workdir: str, target: str | None = None) -> dict:
    """Run pytest tests in a sandboxed environment.

    Args:
        workdir: The sandboxed working directory
        target: Optional test file/dir to run (e.g., "tests/test_calc.py")

    Returns:
        Dict with keys: passed, failed, errors, raw
        raw: the raw pytest output
    """
    cmd = ["python", "-m", "pytest", "-q", "--tb=short"]
    if target:
        cmd.append(target)

    result = run_in_sandbox(cmd, workdir, timeout=60)
    raw_output = result.stdout.decode(errors="replace")
    if result.stderr:
        raw_output += result.stderr.decode(errors="replace")

    parsed = _parse_pytest_output(raw_output)
    return parsed
