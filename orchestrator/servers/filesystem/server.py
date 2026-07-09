"""MCP server: workspace-scoped filesystem access (docs/architecture.md #5)."""

from __future__ import annotations

import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from orchestrator.servers.filesystem import ops

_DEFAULT_WORKSPACE = "."

mcp = FastMCP("triarc-filesystem")
_workspace = Path(os.environ.get("TRIARC_WORKSPACE", _DEFAULT_WORKSPACE))


@mcp.tool()
def read_file(path: str) -> str:
    """Read a file's contents by PATH, relative to the workspace root."""
    return ops.read_file(_workspace, path)


@mcp.tool()
def write_file(path: str, content: str) -> None:
    """Write CONTENT to PATH, relative to the workspace root, creating parents as needed."""
    ops.write_file(_workspace, path, content)


@mcp.tool()
def list_dir(path: str = ".") -> list[str]:
    """List entries under PATH, relative to the workspace root."""
    return ops.list_dir(_workspace, path)


if __name__ == "__main__":
    mcp.run()
