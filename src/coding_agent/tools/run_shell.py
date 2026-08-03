from __future__ import annotations

import shlex

from ..sandbox.workdir import run_in_sandbox
from ..sandbox.guardrails import is_command_allowed
from ..obs import observed


@observed(name="tool.run_shell", as_type="tool")
def run_shell(workdir: str, cmd: str, timeout: int = 30) -> dict:
    """Run a shell command in a sandboxed environment.

    Args:
        workdir: The sandboxed working directory
        cmd: Command string to execute
        timeout: Timeout in seconds (default 30)

    Returns:
        Dict with keys: returncode (int), stdout (str), stderr (str)
        If command is blocked: {returncode: -1, stderr: "blocked"}
    """
    # Check if command is allowed
    if not is_command_allowed(cmd):
        return {"returncode": -1, "stderr": "blocked", "stdout": ""}

    # Parse command into a list for subprocess
    try:
        cmd_list = shlex.split(cmd)
    except ValueError:
        # Fallback: split on spaces if shlex fails
        cmd_list = cmd.split()

    # Run in sandbox
    result = run_in_sandbox(cmd_list, workdir, timeout=timeout)

    return {
        "returncode": result.returncode,
        "stdout": result.stdout.decode(errors="replace"),
        "stderr": result.stderr.decode(errors="replace"),
    }
