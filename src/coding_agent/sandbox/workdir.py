from __future__ import annotations
import os, shutil, subprocess, tempfile
from .limits import SAFE_ENV, set_rlimits

_ROOT = os.path.join(tempfile.gettempdir(), "coding_agent")


def make_workdir(task_id: str) -> str:
    os.makedirs(_ROOT, exist_ok=True)
    wd = os.path.join(_ROOT, task_id)
    os.makedirs(wd, exist_ok=True)
    return wd


def cleanup(workdir: str) -> None:
    shutil.rmtree(workdir, ignore_errors=True)


def run_in_sandbox(
    cmd: list[str], workdir: str, *, timeout: int = 30, extra_env: dict | None = None,
) -> subprocess.CompletedProcess:
    env = dict(SAFE_ENV)
    env["HOME"] = workdir
    if extra_env:
        env.update(extra_env)
    kwargs: dict = {
        "cwd": workdir, "env": env, "capture_output": True, "timeout": timeout,
    }
    import sys as _s
    if _s.platform == "linux":
        kwargs["preexec_fn"] = set_rlimits
    try:
        return subprocess.run(cmd, **kwargs)
    except subprocess.TimeoutExpired as e:
        return subprocess.CompletedProcess(
            args=cmd, returncode=124,
            stdout=e.stdout or b"", stderr=(e.stderr or b"") + b"\n[timeout]",
        )
