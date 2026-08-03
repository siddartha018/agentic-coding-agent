from __future__ import annotations
import os, re

_BLOCKED_PATTERNS = [
    re.compile(r"^\s*(sudo|su)\b"),
    re.compile(r"\b(curl|wget|nc|ncat|ssh|scp|sftp|rsync)\b"),
    re.compile(r"\bpip\s+install\b"),
    re.compile(r"\bnpm\s+install\b"),
    re.compile(r"\byarn\s+add\b"),
    re.compile(r"\bchmod\b"),
    re.compile(r"\brm\s+-rf\s+/(\s|$)"),
    re.compile(r">/etc/"),
    re.compile(r">>/etc/"),
]


def is_command_allowed(cmd: str) -> bool:
    for p in _BLOCKED_PATTERNS:
        if p.search(cmd):
            return False
    return True


def is_path_in_workdir(path: str, workdir: str) -> bool:
    try:
        p_abs = os.path.realpath(path)
        w_abs = os.path.realpath(workdir)
    except OSError:
        return False
    return p_abs == w_abs or p_abs.startswith(w_abs + os.sep)
