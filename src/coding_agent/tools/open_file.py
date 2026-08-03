from __future__ import annotations

from pathlib import Path

from ..sandbox.guardrails import is_path_in_workdir
from ..obs import observed


@observed(name="tool.open_file", as_type="tool")
def open_file(workdir: str, path: str, start: int | None = None, end: int | None = None) -> str:
    """Open and read a file within workdir.

    Args:
        workdir: The sandboxed working directory
        path: Path to the file (must be within workdir)
        start: Optional start line (1-indexed, inclusive)
        end: Optional end line (1-indexed, inclusive)

    Returns:
        File contents (up to 400 lines)

    Raises:
        PermissionError: If path is outside workdir
        FileNotFoundError: If file doesn't exist
    """
    if not is_path_in_workdir(path, workdir):
        raise PermissionError(f"Path {path} is outside workdir {workdir}")

    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {path}")

    content = p.read_text(errors="replace")
    lines = content.splitlines(keepends=True)

    # Limit to 400 lines
    max_lines = 400
    if len(lines) > max_lines:
        lines = lines[:max_lines]

    # Apply start/end filtering if provided
    if start is not None or end is not None:
        start_idx = (start - 1) if start else 0
        end_idx = end if end else len(lines)
        lines = lines[start_idx:end_idx]

    return "".join(lines)
