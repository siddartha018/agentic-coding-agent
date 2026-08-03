# Agentic Coding Assistant — Design Spec (revised)

**Status:** Approved (revised 2026-07-31 — sandbox switched from Docker to
Python subprocess after office-laptop no-install constraint surfaced)
**Owner:** enldias

## 1. Problem

Given `(repo, issue_text)`, produce a unified diff that fixes the bug and
makes the repo's test suite pass. This is the SWE-agent archetype — the
single most-screened project by agent-eng teams (Cursor, Cognition, Cody).

## 2. Non-goals

- Beat SWE-bench Verified — not the point of a portfolio build.
- Multi-language beyond Python (Python-only tree-sitter grammars).
- Long-running IDE plugin. Batch CLI + FastAPI endpoint only.
- Strong isolation. We're building on an office laptop where Docker can't
  be installed; the sandbox is best-effort process-level isolation. This
  is documented, not hidden.

## 3. Success criteria

Measurable acceptance targets in `evals/`:

| Metric | Target |
|---|---|
| **Mini-bench resolved rate** (our 20 hand-curated tasks) | ≥ 40% (8/20) |
| Tool-call success rate (parses + executes) | ≥ 0.95 |
| Median tokens per solved task | ≤ 200k |
| Median wall-clock per task | ≤ 6 min |
| Sandbox red-team pass rate (10 escape attempts caught) | ≥ 0.80 |
| Cost | $0 |

The 40% target is realistic because the mini-bench is hand-curated to be
solvable by a well-instrumented agent — unlike SWE-bench Lite, which
mixes trivial and nearly-impossible tasks. Hosted commercial agents sit
around 40–55% on SWE-bench Lite; we aim for parity on an equivalent-
difficulty custom set.

## 4. Architecture

LangGraph state machine. One control loop, three action types.

```
   (repo, issue)
        │
   ┌────▼────┐
   │  index  │  walk repo → tree-sitter chunks → embed → Qdrant per-run
   └────┬────┘
        │
   ┌────▼─────┐
   │  plan    │  reasoner LLM writes scratchpad: relevant files, test to run
   └────┬─────┘
        │
   ┌────▼──────────┐
   │  act (agent)  │  ReAct loop: search_code, open_file, edit_file,
   └────┬──────────┘  run_shell, run_tests, submit
        │
   ┌────▼──────┐
   │  observe  │  parse test output; pass → done, else repair
   └────┬──────┘
        │
   ┌────▼──────┐
   │  repair   │  reasoner reads failure + diff, updates scratchpad,
   └────┬──────┘  loops back to `act` (cap = 4)
        ▼
      diff
```

### 4.1 Tools

All tools execute in a **per-task Python subprocess sandbox** (§4.3). Host
filesystem is never mutated by the agent — the repo is copied into a temp
work-directory that gets removed on task end.

| Tool | Signature | Notes |
|---|---|---|
| `search_code(query, k=8)` | Hybrid Qdrant retrieval over indexed chunks. Returns `[{file, symbol, start_line, end_line, snippet}]`. |
| `open_file(path, start?, end?)` | Reads from work-directory. Max 400 lines returned. Rejects absolute paths outside work-dir. |
| `edit_file(path, old, new)` | Exact-match replace, `old` must appear exactly once. Fails loudly on ambiguity. |
| `run_shell(cmd, timeout=30)` | `subprocess.run(cmd, cwd=workdir, capture_output=True, timeout=timeout, env=STRIPPED_ENV)`. See §4.3 for guardrails. |
| `run_tests(target?)` | Runs `pytest` (or the repo's declared test cmd) with `--tb=short -q`. Parses pass/fail counts. |
| `submit(diff)` | Emits final unified diff via `git -C workdir diff` — ends the run. |

### 4.2 Repo indexing

- Copy repo into `/tmp/coding_agent/<task_id>/` (via `shutil.copytree`).
- Walk tracked files (or all `.py` files if no `.git`), skipping binaries,
  `__pycache__`, `.venv`, `node_modules`, `.git`.
- **tree-sitter (Python only)** — one chunk per function/class, plus a
  whole-file chunk when < 1200 tokens.
- Embed via Gemini `gemini-embedding-001` with local BGE-base-en-v1.5
  fallback (same 768-dim, same pattern proven in Project 1).
- Upsert to Qdrant collection `repo_<task_id>` with payload
  `{path, symbol, start_line, end_line, text}` + sparse BM25 vector.

### 4.3 Sandbox — Python subprocess

**Isolation this sandbox provides (documented honestly):**

- ✅ Work-directory quarantine — every tool operates inside
  `/tmp/coding_agent/<task_id>/`; path traversal blocked at tool layer.
- ✅ Environment scrub — `subprocess.run(..., env={"PATH": SAFE_PATH,
  "HOME": workdir, "PYTHONDONTWRITEBYTECODE": "1"})`. `.env` and secrets
  in the parent process do NOT reach subprocess.
- ✅ Wall-clock timeout — `timeout=30` per shell call, `timeout=120` per
  test run, task-level cap 10 min.
- ✅ Memory + CPU limits on Linux — `preexec_fn=_set_rlimits` sets
  `RLIMIT_AS=1GB`, `RLIMIT_CPU=60s`, `RLIMIT_NPROC=32`.
- ✅ Network disabled — `env["NO_PROXY"]="*"` + `env["http_proxy"]=""` +
  `unshare -n` when available (rare on WSL2 without root); documented
  fallback: block egress at the tool layer by rejecting any shell command
  that starts with `curl|wget|nc|ssh|scp|pip install|npm install`.
- ✅ Read-only host — no bind-mounts, no `docker cp`; work-dir is a
  disposable copy.
- ✅ Sandbox red-team eval — 10 explicit escape attempts verified refused.

**Isolation this sandbox does NOT provide (documented):**

- ❌ Kernel-level isolation — a Python subprocess shares the kernel. A
  malicious repo running arbitrary code could theoretically exploit
  kernel bugs (same as Docker on shared-kernel).
- ❌ Non-Linux enforcement — `RLIMIT_*` and `unshare` are Linux-only. On
  macOS/Windows the sandbox degrades to just workdir + timeout + env
  scrub. Documented.
- ❌ Perfect network block without root — on WSL2 without `unshare`
  permission, we rely on the shell-command allowlist + env scrub.

This is a portfolio project. The threat model is *known-friendly inputs*
(our own mini-bench + the user's own repos), not adversarial code.

### 4.4 State (`AgentState`)

```python
class AgentState(TypedDict):
    task_id: str
    workdir: str                # /tmp/coding_agent/<task_id>/
    issue: str
    scratchpad: str             # planner + repair write; act reads
    messages: Annotated[list, add_messages]
    diff: str | None
    tests_passed: bool | None
    iterations: int
```

### 4.5 Models (all Groq — Gemini fallback via project-1 pattern)

| Node | Model | Rationale |
|---|---|---|
| planner / repair | `llama-3.3-70b-versatile` (Groq) | Better reasoning for scratchpad; long context. |
| act (tool routing) | `llama-3.1-8b-instant` (Groq) | Fast, cheap, tool-calling reliable. |

Fallback: 3× Groq retry on 429 with exponential backoff, then Gemini
`gemini-flash-latest`. Same `llm.py` pattern as Project 1.

### 4.6 Termination

- `submit(diff)` called AND tests pass → success.
- Iteration cap = 4 repair loops → failure.
- Wall-clock cap = 10 min → failure.
- Sandbox violation (path traversal, blocked command, timeout exceeded)
  → immediate abort, logged.

### 4.7 Observability

Langfuse `@observed` on every node and every tool (agent / retriever /
tool types). Each mini-bench run is one Langfuse session
(`session_id = task_id`). RAGAS-style scoring hooks: after each task
records `resolved` (0/1) and `tokens_used` via `obs.score_current(...)`.

## 5. Mini-benchmark (in place of SWE-bench Lite)

`evals/minibench/tasks/` — 20 hand-curated Python bug-fixing tasks.
Each task is a self-contained directory:

```
tasks/task-01-off-by-one/
├── task.json           # {issue, expected_files_touched}
├── src/
│   └── calc.py         # broken function
└── tests/
    └── test_calc.py    # failing pytest
```

Task types (rough mix):
- 5 × easy: off-by-one / typo / missing return / wrong operator.
- 10 × medium: state-management bug, dict-vs-list confusion, missing
  edge-case handling, wrong regex, generator-vs-list bug.
- 5 × hard: multi-file changes, subtle async ordering, requires reading
  a helper module the issue doesn't name.

`evals/run_benchmark.py` for each task:
1. `shutil.copytree` fixture into `/tmp/coding_agent/<task_id>/`.
2. Run baseline test — must FAIL (proves task is well-formed).
3. Run agent with `issue` from `task.json`.
4. Re-run baseline test → pass/fail → resolved.
5. Record `{task_id, resolved, iterations, tokens, wall_clock}`.

Resume-safe (writes per-task JSON so partial runs are retained).

## 6. Repo layout

```
02-agentic-coding-assistant/
├── pyproject.toml
├── .env.example
├── README.md
├── docs/
│   ├── spec.md              (this file)
│   └── plans/2026-07-31-agentic-coding-assistant.md
├── src/coding_agent/
│   ├── config.py
│   ├── obs.py               # Langfuse wrapper (reuse Project 1 pattern)
│   ├── llm.py               # Groq→Gemini with retry + local embed fallback
│   ├── state.py             # AgentState
│   ├── graph.py             # LangGraph wiring: index→plan→act→observe→(done|repair)
│   ├── cli.py               # python -m coding_agent.cli --repo <path> --issue "..."
│   ├── api.py               # POST /solve, SSE
│   ├── nodes/
│   │   ├── index.py         # one-shot repo indexing
│   │   ├── plan.py          # reasoner writes scratchpad
│   │   ├── act.py           # create_react_agent, bound to tools
│   │   ├── observe.py       # parse test output
│   │   └── repair.py        # reasoner updates scratchpad from failure
│   ├── tools/
│   │   ├── search_code.py
│   │   ├── open_file.py
│   │   ├── edit_file.py
│   │   ├── run_shell.py
│   │   ├── run_tests.py
│   │   └── submit.py
│   ├── sandbox/
│   │   ├── workdir.py       # per-task tempdir + copytree + cleanup
│   │   ├── limits.py        # rlimit helpers, timeout, env scrub
│   │   └── guardrails.py    # command allowlist, path traversal check
│   └── indexing/
│       ├── tree_sitter_chunk.py
│       ├── embed.py
│       └── qdrant.py
├── tests/                   # unit tests, all mocked (no live API)
│   ├── test_sandbox_isolation.py
│   ├── test_edit_file.py
│   ├── test_chunk.py
│   ├── test_search_code.py
│   ├── test_graph_smoke.py
│   ├── ...
└── evals/
    ├── minibench/
    │   └── tasks/                 # 20 hand-curated task dirs
    ├── run_benchmark.py           # resume-safe
    ├── red_team/
    │   └── sandbox_escape.py      # 10 escape attempts
    └── results/
```

## 7. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Groq 429 mid-benchmark | 3× retry with backoff → Gemini fallback (proven in Project 1); resume-safe results. |
| Sandbox is subprocess-level, not container-level | Documented honestly in spec + README; red-team eval verifies 10 concrete escape attempts refused. |
| Agent gets stuck in edit loops | Iteration cap = 4, token cap per task, wall-clock cap 10 min. |
| Free-tier daily quota exhausted | Same resume-safe eval pattern; can pause and resume days apart. |
| Repos with dependencies we can't install (numpy, etc.) | Mini-bench tasks use only stdlib + `pytest`. No `pip install` needed inside sandbox. |
| Tree-sitter grammar install | `tree-sitter-python` wheel is available on PyPI, no compilation needed. |

## 8. Out of scope

- Non-Python repos.
- PR posting / GitHub integration.
- Custom fine-tuned models.
- Multi-file architectural rewrites in one shot (agent can chain them via
  multiple `edit_file` calls, but no "refactor whole module" tool).
