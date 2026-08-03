"""CLI for the coding agent."""
from __future__ import annotations

import argparse
import sys
import uuid

from .graph import run


def main() -> None:
    """CLI entry point for the coding agent.

    Usage:
        python -m coding_agent.cli --repo /path/to/repo --issue "Bug: ..." [--task-id uuid]

    Behavior:
        1. Parse CLI args
        2. Call graph.run(repo_path, issue, task_id)
        3. Extract final diff from result["diff"]
        4. Print diff to stdout
        5. Exit with code 0 if tests_passed=True, else 1
    """
    parser = argparse.ArgumentParser(
        description="Agentic coding assistant — solve issues in repos"
    )
    parser.add_argument(
        "--repo",
        required=True,
        help="Path to the repository",
    )
    parser.add_argument(
        "--issue",
        required=True,
        help="Issue or task description",
    )
    parser.add_argument(
        "--task-id",
        default=None,
        help="Task UUID (generated if not provided)",
    )

    args = parser.parse_args()

    task_id = args.task_id or uuid.uuid4().hex
    try:
        result = run(args.repo, args.issue, task_id)

        # Print final diff to stdout
        diff = result.get("diff", "")
        if diff:
            print(diff)

        # Exit with code based on tests_passed
        tests_passed = result.get("tests_passed", False)
        sys.exit(0 if tests_passed else 1)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
