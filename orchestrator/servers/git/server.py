"""MCP server: git operations scoped to a workspace (docs/architecture.md #5)."""

from __future__ import annotations

import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from orchestrator.servers.git import ops

_DEFAULT_WORKSPACE = "."

mcp = FastMCP("triarc-git")
_workspace = Path(os.environ.get("TRIARC_WORKSPACE", _DEFAULT_WORKSPACE))


@mcp.tool()
def clone(url: str, dest: str) -> dict:
    """Clone URL into DEST inside the workspace."""
    return ops.clone(_workspace, url, dest)


@mcp.tool()
def branch(name: str) -> dict:
    """Create and switch to a new branch NAME."""
    return ops.branch(_workspace, name)


@mcp.tool()
def diff(paths: list[str] | None = None) -> dict:
    """Show the working-tree diff, optionally scoped to PATHS."""
    return ops.diff(_workspace, paths)


@mcp.tool()
def commit(message: str, paths: list[str] | None = None) -> dict:
    """Stage PATHS (or all changes) and commit with MESSAGE."""
    return ops.commit(_workspace, message, paths)


if __name__ == "__main__":
    mcp.run()
