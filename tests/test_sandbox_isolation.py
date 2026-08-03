import os, tempfile
import pytest
from coding_agent.sandbox.guardrails import is_command_allowed, is_path_in_workdir
from coding_agent.sandbox.workdir import make_workdir, cleanup, run_in_sandbox


@pytest.mark.parametrize("cmd", [
    "curl http://example.com",
    "wget http://example.com",
    "nc -l 1234",
    "ssh user@host",
    "scp file host:/",
    "pip install requests",
    "npm install left-pad",
    "sudo rm -rf /",
    "chmod 777 /etc/passwd",
])
def test_disallowed_commands(cmd):
    assert is_command_allowed(cmd) is False


@pytest.mark.parametrize("cmd", [
    "pytest tests/",
    "python -c 'print(1)'",
    "ls -la",
    "cat calc.py",
    "git diff",
])
def test_allowed_commands(cmd):
    assert is_command_allowed(cmd) is True


def test_path_traversal_blocked(tmp_path):
    wd = str(tmp_path / "w")
    os.makedirs(wd)
    assert is_path_in_workdir(f"{wd}/x.py", wd) is True
    assert is_path_in_workdir("/etc/passwd", wd) is False
    assert is_path_in_workdir(f"{wd}/../../../etc/passwd", wd) is False


def test_run_in_sandbox_timeout():
    wd = make_workdir("t-timeout")
    try:
        r = run_in_sandbox(["sh", "-c", "sleep 5"], wd, timeout=1)
        assert r.returncode != 0
    finally:
        cleanup(wd)


def test_run_in_sandbox_captures_stdout():
    wd = make_workdir("t-stdout")
    try:
        r = run_in_sandbox(["echo", "hello"], wd)
        assert r.stdout.decode().strip() == "hello"
    finally:
        cleanup(wd)


def test_run_in_sandbox_strips_secret_env(monkeypatch):
    monkeypatch.setenv("MY_SECRET", "s3cret")
    wd = make_workdir("t-env")
    try:
        r = run_in_sandbox(["sh", "-c", "echo $MY_SECRET"], wd)
        assert "s3cret" not in r.stdout.decode()
    finally:
        cleanup(wd)
