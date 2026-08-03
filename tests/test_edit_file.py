import pytest
from coding_agent.tools.edit_file import edit_file


def test_replaces_unique_match(tmp_path):
    """Test that a unique match is correctly replaced."""
    p = tmp_path / "calc.py"
    p.write_text("def add(a, b):\n    return a - b\n")
    edit_file(str(tmp_path), str(p), "return a - b", "return a + b")
    assert p.read_text() == "def add(a, b):\n    return a + b\n"


def test_ambiguous_old_raises(tmp_path):
    """Test that ambiguous (non-unique) patterns raise ValueError."""
    p = tmp_path / "x.py"
    p.write_text("x = 1\nx = 1\n")
    with pytest.raises(ValueError, match="not unique"):
        edit_file(str(tmp_path), str(p), "x = 1", "x = 2")


def test_missing_file_raises(tmp_path):
    """Test that editing a non-existent file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        edit_file(str(tmp_path), str(tmp_path / "nope.py"), "a", "b")


def test_rejects_path_outside_workdir(tmp_path):
    """Test that paths outside the workdir are rejected with PermissionError."""
    (tmp_path / "wd").mkdir()
    outside = tmp_path / "outside.py"
    outside.write_text("hi")
    with pytest.raises(PermissionError):
        edit_file(str(tmp_path / "wd"), str(outside), "hi", "bye")


def test_pattern_not_found_raises(tmp_path):
    """Test that a non-existent pattern raises ValueError."""
    p = tmp_path / "x.py"
    p.write_text("x = 1\n")
    with pytest.raises(ValueError, match="not found"):
        edit_file(str(tmp_path), str(p), "y = 2", "z = 3")
