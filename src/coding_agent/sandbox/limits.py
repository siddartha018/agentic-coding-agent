from __future__ import annotations
import os
import sys

SAFE_PATH = "/usr/local/bin:/usr/bin:/bin"

SAFE_ENV: dict[str, str] = {
    "PATH": SAFE_PATH,
    "LANG": "C.UTF-8",
    "LC_ALL": "C.UTF-8",
    "PYTHONDONTWRITEBYTECODE": "1",
    "PYTHONIOENCODING": "utf-8",
    "http_proxy": "",
    "https_proxy": "",
    "HTTP_PROXY": "",
    "HTTPS_PROXY": "",
    "no_proxy": "*",
}


def set_rlimits() -> None:
    """preexec_fn: apply RLIMIT_AS, RLIMIT_CPU, RLIMIT_NPROC. Linux-only."""
    if sys.platform != "linux":
        return
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (1 << 30, 1 << 30))  # 1 GB
        resource.setrlimit(resource.RLIMIT_CPU, (60, 60))
        resource.setrlimit(resource.RLIMIT_NPROC, (32, 32))
    except Exception:
        pass
