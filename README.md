# Agentic Coding Assistant

A LangGraph SWE-agent that fixes Python bugs by navigating a repo, editing code in a sandboxed workdir, and self-repairing against tests. Benchmarked on a 20-task hand-curated mini-bench.

## Table of Contents

- [Why This Project](#why-this-project)
- [Architecture](#architecture)
- [Stack](#stack)
- [Quickstart](#quickstart)
- [How to Test](#how-to-test)
- [Design Spec](#design-spec)
- [Repo Layout](#repo-layout)
- [Mini-Bench Methodology](#mini-bench-methodology)
- [Sandbox Red-Team](#sandbox-red-team)
- [Observability (Langfuse)](#observability-langfuse)
- [Guardrails](#guardrails)
- [Known Limitations](#known-limitations)
- [Roadmap](#roadmap)

## Why This Project



| Capability | Code Location | Interview Defense |
|---|---|---|
| **Multi-step planning** | `nodes/plan.py` + `nodes/repair.py` | "The planner LLM writes a scratchpad with relevant files and test targets; the repair node updates it on failure. This separates reasoning from action." |
| **RAG for repo context** | `indexing/tree_sitter_chunk.py`, `indexing/qdrant.py`, `tools/search_code.py` | "Tree-sitter chunks code by symbol, Qdrant hybrid search (dense + BM25) retrieves top-k. Handles large repos beyond LLM context window." |
| **Sandboxed tool use** | `sandbox/guardrails.py`, `sandbox/limits.py`, `tools/run_shell.py` | "Python subprocess sandbox with workdir isolation, rlimit enforcement, command allowlist, timeout guards. Red-team eval verifies 100% block rate." |
| **Self-repair loop** | `graph.py` routes observe→repair→act | "On test failure, reasoner reads diff + error, updates scratchpad, retries up to 4 iterations. Mirrors how SWE-bench agents recover." |
| **Guardrails (5 layers)** | `sandbox/`, `tools/`, `graph.py` | "Path traversal checks, command allowlist, memory/CPU limits, iteration cap, timeout enforcement — see Guardrails section." |
| **Evals (3 tiers)** | `tests/`, `evals/run_benchmark.py`, `evals/red_team/` | "47 unit tests (no API keys), 20-task mini-bench, 10-attack red-team. Resume-safe for free-tier quotas." |
| **LLM fallback** | `llm.py` | "Groq with 3× exponential backoff, then Gemini fallback. Same pattern used in Project 1." |

## Architecture

```
     (repo, issue)
          │
     ┌────▼────┐
     │  index  │  Walk repo → tree-sitter chunks → embed → Qdrant per-task collection
     └────┬────┘
          │
     ┌────▼─────┐
     │   plan   │  Reasoner LLM writes scratchpad: relevant files, test target
     └────┬─────┘
          │
     ┌────▼─────────┐
     │  act (agent) │  ReAct loop: search_code, open_file, edit_file, run_shell, run_tests, submit
     └────┬─────────┘
          │
     ┌────▼──────┐
     │  observe  │  Parse test output → pass = done, fail = repair
     └────┬──────┘
          │
     ┌────▼──────┐       tests_passed? ──yes──> END
     │  repair   │
     └────┬──────┘
          │
          └─── iterations < 4? ──yes──> loop back to act
                                 no ──> END
```

## Stack

| Layer | Choice | Why |
|---|---|---|
| **Orchestration** | LangGraph 1.0.6 | State machine with conditional edges for observe→(done\|repair). First-class streaming. |
| **Reasoner LLM** | Groq llama-3.3-70b-versatile | Long context (128k), better reasoning for scratchpad + repair. Free tier. |
| **Actor LLM** | Groq llama-3.1-8b-instant | Fast tool routing, cheap. Proven reliable for tool-calling. |
| **Fallback LLM** | Gemini Flash | Groq 429 → 3× retry with backoff → Gemini. Same pattern as Project 1. |
| **Embeddings** | Gemini text-embedding-004 + FastEmbed BGE-base-en-v1.5 fallback | 768-dim, proven in Project 1. Local fallback for rate limits. |
| **Vector DB** | Qdrant Cloud | Hybrid search (dense + sparse BM25). Per-task collections, auto-cleanup. |
| **Code parsing** | tree-sitter-python | Symbol-level chunking (function/class). AST-aware, handles nested defs. |
| **Sandbox** | Python subprocess + rlimit | Workdir isolation, memory/CPU caps, timeout, command allowlist. Honest limitations documented. |
| **Serving** | FastAPI + SSE | POST /solve streams plan, tool_call, test_result, done events. |
| **Observability** | Langfuse 3.0 | @observe on every node + tool. Session = task_id. RAGAS-style scoring. |
| **Persistence** | SQLite (Langfuse SDK) | Traces buffered, flushed on task end. |
| **Eval** | 20-task hand-curated mini-bench | Mix of easy/medium/hard. Resume-safe runner for free-tier quotas. |

## Quickstart

**Prerequisites:** Python 3.11+, Groq/Gemini/Qdrant free-tier accounts.

```bash
# 1. Clone and setup
cd agentic-coding-agent
python -m venv .venv && source .venv/bin/activate
pip install -e .

# 2. Configure .env
cp .env.example .env
# Add: GROQ_API_KEY, GEMINI_API_KEY, QDRANT_URL, QDRANT_API_KEY
# Optional: LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY for tracing

# 3. One-shot CLI demo (fix a toy bug)
coding-agent --repo evals/minibench/tasks/task-01-off-by-one --issue "Fix the off-by-one error in sum_range"

# 4. Streaming API demo
uvicorn coding_agent.api:app --reload
curl -X POST http://localhost:8000/solve \
  -H "Content-Type: application/json" \
  -d '{"repo_path": "evals/minibench/tasks/task-01-off-by-one", "issue": "Fix off-by-one"}' \
  --no-buffer
# Watch SSE events: plan → tool_call → tool_result → test_result → done
```

## How to Test

Three tiers mirroring Project 1's structure:

### Tier 1: Unit tests (no API keys required)

```bash
pytest -v
# 47 tests: graph wiring, sandbox isolation, tool contracts, parsing, SSE events
# Mocked LLMs, in-memory Qdrant, fixture repos
# Runtime: <10 seconds
```

### Tier 2: Live sanity pings (requires API keys)

```bash
# Verify Groq + Gemini + Qdrant connectivity
python -c "from coding_agent.llm import get_llm; print(get_llm('reasoner').invoke('hi').content[:50])"
python -c "from coding_agent.indexing.qdrant import _get_client; print(_get_client().get_collections())"
```

### Tier 3: Full mini-bench + sandbox red-team (requires API keys)

```bash
# Mini-bench: 20 tasks, resume-safe (skips completed tasks)
python evals/run_benchmark.py --out evals/results/
# Expected: ≥40% resolved (8/20), median <6 min/task, <200k tokens/task
# Runtime: 60-120 min (rate-limited on free tier)

# Sandbox red-team: 10 escape attempts
python -m pytest tests/test_red_team_sandbox.py -v
# Expected: 100% blocked (10/10)
```


