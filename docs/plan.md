# Agentic Coding Assistant — Implementation Plan

Sequential milestones. Estimated total: 6–8 focused days (this is the biggest
of the three).

## M0 — Scaffold (0.5 day)

- [ ] `pyproject.toml`: `langgraph`, `groq`, `google-genai`, `openai` (for
      OpenRouter), `qdrant-client[fastembed]`, `tree-sitter`,
      `tree-sitter-python`, `tree-sitter-javascript`, `docker`,
      `langfuse`, `fastapi`, `uvicorn`, `datasets` (SWE-bench).
- [ ] `.env.example`.
- [ ] `config.py` (`pydantic-settings`).
- [ ] `llm.py` — Groq + Gemini + OpenRouter with router (`primary`,
      `fast`, `fallback` names).

## M1 — Sandbox (1 day)

- [ ] `sandbox/docker.py` — `Sandbox` context manager: build image, mount
      workdir volume, network-off by default, CPU/mem limits.
- [ ] `sandbox/limits.py` — enforce timeouts on `docker exec`.
- [ ] Tests:
  - `test_sandbox_isolation.py` — commands inside cannot reach host
    filesystem or the internet; container is destroyed on exit; timeouts
    kill runaway processes.

## M2 — Repo indexing (1 day)

- [ ] `indexing/tree_sitter_chunk.py` — walk repo, chunk per symbol via
      tree-sitter grammars, fall back to line-window for unsupported files.
- [ ] `indexing/embed.py` — Gemini batched embeddings.
- [ ] `indexing/qdrant.py` — per-task collection, dense + sparse (BM25) via
      FastEmbed.
- [ ] `tools/search_code.py` — hybrid `query_points` with RRF fusion.
- [ ] Test `test_chunk.py`: on a fixture repo, every top-level def/class
      becomes exactly one chunk; ranges line up with source.

## M3 — Tools (1 day)

- [ ] `tools/open_file.py` — read via `docker cp` or `docker exec cat`, cap
      400 lines, support ranges.
- [ ] `tools/edit_file.py` — read file, assert unique `old`, replace, write
      back; fail cleanly on ambiguity.
- [ ] `tools/run_shell.py` — bounded `docker exec`; capture stdout/stderr.
- [ ] `tools/run_tests.py` — configurable command; parse pytest/junit output
      into `{passed, failed, errors}`.
- [ ] `tools/submit.py` — pure function producing unified diff via `git diff`
      inside sandbox.
- [ ] Test `test_edit_file.py`: ambiguous old-string raises, unique
      old-string replaces once, non-existent file raises.

## M4 — Agent graph (2 days)

- [ ] `state.py` — `AgentState`.
- [ ] `nodes/index.py` — one-shot repo indexing.
- [ ] `nodes/plan.py` — reasoner writes scratchpad from `issue` + top-k
      retrieved chunks.
- [ ] `nodes/act.py` — `create_react_agent` bound to all tools, using fast
      model.
- [ ] `nodes/observe.py` — parse `run_tests` output → set `tests_passed`.
- [ ] `nodes/repair.py` — reasoner reads failure + diff, updates scratchpad.
- [ ] `graph.py` — wire: `index → plan → act → observe → (done | repair →
      act)`, cap iterations.
- [ ] `test_graph_smoke.py` — synthetic 1-file repo with a broken function
      and a failing test; agent must fix it in ≤ 2 iterations.

## M5 — Serving (0.5 day)

- [ ] `cli.py` — `python -m coding_agent.cli --repo <path> --issue "..."`.
- [ ] `api.py` — `POST /solve` (async) → returns `task_id`; `GET /solve/{task_id}`
      streams SSE events (`plan`, `tool_call`, `tool_result`, `test_result`,
      `done`).

## M6 — Observability (0.5 day)

- [ ] Langfuse `@observe` on nodes, tools, LLM calls.
- [ ] Attach `task_id` to every span.

## M7 — SWE-bench Lite subset (1.5 days)

- [ ] `evals/swebench_lite/task_ids.json` — curated 20-task list (aim for a
      mix: 5 easy, 10 medium, 5 hard).
- [ ] `evals/run_benchmark.py` — resume-safe: loads dataset, iterates tasks,
      writes `results/tasks/<id>.json` per task; skips if file exists.
- [ ] `evals/red_team/sandbox_escape.py` — 10 payloads.
- [ ] Commit a baseline results file after a full run.

## M8 — Polish (0.5 day)

- [ ] README demo: one CLI invocation on a toy repo + Langfuse screenshot +
      link to `evals/results/summary.csv`.
- [ ] "What I'd do next": self-consistency across N attempts, better retrieval
      (embedding-per-symbol AST search), a Python-and-JS-only reranker.

## Acceptance gate

Latest `evals/results/summary.csv` shows ≥ 20% resolved on the 20-task
subset, ≥ 95% tool-call success, and 100% sandbox red-team pass.
