#!/usr/bin/env python3
"""
Resume-safe benchmark runner for mini-bench tasks.

For each task:
1. Check if results/<task_id>.json exists; skip if yes.
2. Copy task fixture into a temporary directory.
3. Call coding_agent.graph.run(repo=tempdir, issue=task.json['issue'], task_id=task_id).
4. Re-run pytest in the task fixture to check if tests pass.
5. Write per-task result JSON: {task_id, resolved: bool, iterations, wall_clock, error?}.
6. Aggregate into results/summary.json at the end.
"""

import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def run_benchmark(tasks_dir: Path, results_dir: Path):
    """Run the benchmark on all tasks in tasks_dir."""
    from coding_agent import obs

    results_dir.mkdir(parents=True, exist_ok=True)

    # Initialize Langfuse at benchmark start
    obs.init_langfuse()

    task_dirs = sorted(tasks_dir.glob("task-*"))
    if not task_dirs:
        print(f"No tasks found in {tasks_dir}", file=sys.stderr)
        return

    print(f"Found {len(task_dirs)} tasks")

    # Create a session ID for the entire benchmark run
    benchmark_session_id = f"minibench-{int(time.time())}"

    # Wrap the benchmark loop in a trace context
    with obs.trace_context(session_id=benchmark_session_id, tags=["minibench"]):
        for task_dir in task_dirs:
            task_id = task_dir.name
            result_file = results_dir / f"{task_id}.json"

            if result_file.exists():
                print(f"[SKIP] {task_id} (result already exists)")
                continue

            print(f"[RUN]  {task_id}")
            task_json_path = task_dir / "task.json"
            if not task_json_path.exists():
                print(f"  ERROR: missing task.json in {task_dir}")
                continue

            task_data = json.loads(task_json_path.read_text())
            issue = task_data.get("issue", "")
            if not issue:
                print(f"  ERROR: empty issue in {task_id}")
                continue

            # Create a temporary working directory by copying the task fixture
            workdir = None
            try:
                workdir = tempfile.mkdtemp(prefix=f"minibench_{task_id}_")
                shutil.copytree(task_dir / "src", Path(workdir) / "src", dirs_exist_ok=True)
                shutil.copytree(task_dir / "tests", Path(workdir) / "tests", dirs_exist_ok=True)
                if (task_dir / "conftest.py").exists():
                    shutil.copy(task_dir / "conftest.py", workdir)

                start_time = time.time()
                agent_state = None
                error_msg = None

                try:
                    # Import here to avoid circular imports and allow the agent to exist
                    from coding_agent.graph import run as agent_run

                    agent_state = agent_run(repo_path=workdir, issue=issue, task_id=task_id)
                except Exception as e:
                    error_msg = f"Agent crashed: {type(e).__name__}: {e}"
                    print(f"  {error_msg}")

                wall_clock = time.time() - start_time

                # Re-run pytest in the workdir to check if the bug is fixed
                resolved = False
                if error_msg is None:
                    try:
                        result = subprocess.run(
                            [sys.executable, "-m", "pytest", "-q", "--tb=short"],
                            cwd=workdir,
                            capture_output=True,
                            timeout=30,
                        )
                        resolved = result.returncode == 0
                    except subprocess.TimeoutExpired:
                        error_msg = "Pytest timeout"
                    except Exception as e:
                        error_msg = f"Pytest error: {e}"

                iterations = agent_state.get("iterations", 0) if agent_state else 0

                # Emit scores for this task
                obs.score_current("resolved", 1.0 if resolved else 0.0)
                obs.score_current("wall_clock_sec", wall_clock)
                obs.score_current("iterations", float(iterations))

                result_data = {
                    "task_id": task_id,
                    "resolved": resolved,
                    "iterations": iterations,
                    "wall_clock": wall_clock,
                }
                if error_msg:
                    result_data["error"] = error_msg

                result_file.write_text(json.dumps(result_data, indent=2))
                status = "PASS" if resolved else "FAIL"
                print(f"  [{status}] {wall_clock:.2f}s, {iterations} iterations")

            finally:
                if workdir:
                    shutil.rmtree(workdir, ignore_errors=True)

    # Flush Langfuse before aggregating results
    obs.flush()

    # Aggregate results into summary.json
    all_results = []
    for result_file in sorted(results_dir.glob("task-*.json")):
        all_results.append(json.loads(result_file.read_text()))

    resolved_count = sum(1 for r in all_results if r.get("resolved", False))
    total = len(all_results)
    summary = {
        "total": total,
        "resolved": resolved_count,
        "pass_rate": resolved_count / total if total > 0 else 0.0,
        "tasks": all_results,
    }
    summary_file = results_dir / "summary.json"
    summary_file.write_text(json.dumps(summary, indent=2))
    print(f"\n=== Summary ===")
    print(f"Resolved: {resolved_count}/{total} ({summary['pass_rate']:.1%})")
    print(f"Results written to {summary_file}")


if __name__ == "__main__":
    repo_root = Path(__file__).parent.parent
    tasks_dir = repo_root / "evals" / "minibench" / "tasks"
    results_dir = repo_root / "evals" / "results"
    run_benchmark(tasks_dir, results_dir)
