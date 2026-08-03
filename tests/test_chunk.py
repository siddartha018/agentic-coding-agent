from pathlib import Path
from coding_agent.indexing.tree_sitter_chunk import chunk_python_file, chunk_repo


def test_chunks_a_single_function(tmp_path):
    p = tmp_path / "calc.py"
    p.write_text("def add(a, b):\n    return a + b\n\ndef sub(a, b):\n    return a - b\n")
    chunks = chunk_python_file(str(p))
    assert len(chunks) >= 2
    symbols = {c.symbol for c in chunks}
    assert "add" in symbols and "sub" in symbols


def test_chunk_repo_skips_venv(tmp_path):
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "junk.py").write_text("def x(): pass\n")
    (tmp_path / "real.py").write_text("def real(): return 1\n")
    chunks = chunk_repo(str(tmp_path))
    paths = {c.path for c in chunks}
    assert any("real.py" in p for p in paths)
    assert not any(".venv" in p for p in paths)
