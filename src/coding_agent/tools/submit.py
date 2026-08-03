from __future__ import annotations

from ..sandbox.workdir import run_in_sandbox
from ..obs import observed


@observed(name="tool.submit", as_type="tool")
def submit(workdir: str) -> str:
    """Get a unified diff of changes made in the workdir.

    If workdir is a git repo, uses `git diff`.
    Otherwise, uses `diff -u` against a `.orig/` backup if available.

    Args:
        workdir: The sandboxed working directory

    Returns:
        Unified diff string (empty if no changes or no git repo)
    """
    # Try git diff first
    result = run_in_sandbox(["git", "-C", workdir, "diff"], workdir, timeout=10)
    if result.returncode == 0 and result.stdout:
        return result.stdout.decode(errors="replace")

    # Fallback: check for .orig/ backup
    import os
    orig_path = workdir + ".orig"
    if os.path.isdir(orig_path):
        result = run_in_sandbox(["diff", "-u", orig_path, workdir], workdir, timeout=10)
        if result.stdout:
            return result.stdout.decode(errors="replace")

    return ""
