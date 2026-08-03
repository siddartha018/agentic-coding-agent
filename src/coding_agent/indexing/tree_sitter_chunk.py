from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path

import tree_sitter_python
from tree_sitter import Language, Parser

_LANG = Language(tree_sitter_python.language())
_PARSER = Parser(_LANG)

_SKIP_DIRS = {".venv", "venv", "__pycache__", ".git", "node_modules", ".pytest_cache", ".mypy_cache"}


@dataclass
class Chunk:
    path: str
    symbol: str
    start_line: int
    end_line: int
    text: str


def _collect(node, source_bytes: bytes, path: str, out: list[Chunk]) -> None:
    if node.type in ("function_definition", "class_definition"):
        name_node = node.child_by_field_name("name")
        symbol = name_node.text.decode("utf-8", errors="replace") if name_node else "<anon>"
        text = source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace")
        out.append(Chunk(
            path=path, symbol=symbol,
            start_line=node.start_point[0] + 1, end_line=node.end_point[0] + 1,
            text=text,
        ))
    for child in node.children:
        _collect(child, source_bytes, path, out)


def chunk_python_file(path: str, *, max_tokens: int = 1200) -> list[Chunk]:
    src = Path(path).read_bytes()
    tree = _PARSER.parse(src)
    out: list[Chunk] = []
    _collect(tree.root_node, src, path, out)
    # Whole-file chunk as fallback if the file is short and produced no top-level symbols.
    if not out and len(src) < max_tokens * 4:
        out.append(Chunk(
            path=path, symbol="<file>", start_line=1,
            end_line=src.count(b"\n") + 1, text=src.decode("utf-8", errors="replace"),
        ))
    return out


def chunk_repo(workdir: str) -> list[Chunk]:
    out: list[Chunk] = []
    for root, dirs, files in os.walk(workdir):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
        for f in files:
            if not f.endswith(".py"):
                continue
            full = os.path.join(root, f)
            try:
                out.extend(chunk_python_file(full))
            except Exception:
                continue
    return out
