from __future__ import annotations

from pathlib import Path

from ..sandbox.guardrails import is_path_in_workdir
from ..obs import observed


@observed(name="tool.edit_file", as_type="tool")
def edit_file(workdir: str, path: str, old: str, new: str) -> str:
    """Replace a unique occurrence of `old` with `new` in a file.

    Args:
        workdir: The sandboxed working directory
        path: Path to the file (must be within workdir)
        old: Exact string to replace (must occur exactly once)
        new: Replacement string

    Returns:
        Confirmation message

    Raises:
        PermissionError: If path is outside workdir
        FileNotFoundError: If file doesn't exist
        ValueError: If `old` occurs 0 times or 2+ times (ambiguous match)
    """
    if not is_path_in_workdir(path, workdir):
        raise PermissionError(f"Path {path} is outside workdir {workdir}")

    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {path}")

    content = p.read_text(errors="replace")

    # Check that `old` appears exactly once
    count = content.count(old)
    if count == 0:
        raise ValueError(f"Pattern not found in {path}")
    if count > 1:
        raise ValueError(f"Pattern occurs {count} times in {path}, not unique")

    # Replace and write back
    new_content = content.replace(old, new, 1)
    p.write_text(new_content)

    return f"Replaced in {path}"
