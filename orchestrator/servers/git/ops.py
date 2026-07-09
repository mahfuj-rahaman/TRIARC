"""Git operations scoped to a workspace directory (docs/features.md #6: clone, branch, diff, commit).

Plain functions over a workspace path so they're testable without an MCP transport;
orchestrator/servers/git/server.py is the MCP-facing wrapper.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def _run(workspace: Path, args: list[str]) -> dict:
    completed = subprocess.run(
        ["git", *args], cwd=str(workspace), capture_output=True, text=True
    )
    return {
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def clone(workspace: Path, url: str, dest: str) -> dict:
    """Clone URL into DEST inside the workspace."""
    return _run(workspace, ["clone", url, dest])


def branch(workspace: Path, name: str) -> dict:
    """Create and switch to a new branch NAME."""
    return _run(workspace, ["checkout", "-b", name])


def diff(workspace: Path, paths: list[str] | None = None) -> dict:
    """Show the working-tree diff, optionally scoped to PATHS."""
    return _run(workspace, ["diff", *(paths or [])])


def commit(workspace: Path, message: str, paths: list[str] | None = None) -> dict:
    """Stage PATHS (or all changes) and commit with MESSAGE."""
    add_result = _run(workspace, ["add", *(paths or ["."])])
    if add_result["exit_code"] != 0:
        return add_result
    return _run(workspace, ["commit", "-m", message])
