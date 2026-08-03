import json
from pathlib import Path

TASKS = Path(__file__).parent.parent / "evals" / "minibench" / "tasks"


def test_all_tasks_are_wellformed():
    dirs = sorted(TASKS.glob("task-*"))
    assert len(dirs) == 20, f"expected 20 tasks, got {len(dirs)}"
    for d in dirs:
        t = json.loads((d / "task.json").read_text())
        assert "issue" in t and t["issue"].strip(), f"missing issue in {d.name}"
        assert "expected_files" in t, f"missing expected_files in {d.name}"
        assert (d / "src").is_dir(), f"missing src/ in {d.name}"
        assert (d / "tests").is_dir(), f"missing tests/ in {d.name}"
        test_files = list((d / "tests").glob("test_*.py"))
        assert test_files, f"no test files in {d.name}/tests/"
