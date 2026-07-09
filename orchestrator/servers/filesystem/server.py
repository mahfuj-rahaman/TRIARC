"""MCP server: workspace-scoped filesystem access (docs/architecture.md #5)."""

from __future__ import annotations

import os
from pathlib import Path

import click
from mcp.server.fastmcp import FastMCP

from orchestrator.security.gates import ConfirmationGateRegistry
from orchestrator.servers.filesystem import ops

_DEFAULT_WORKSPACE = "."

mcp = FastMCP("triarc-filesystem")
_workspace = Path(os.environ.get("TRIARC_WORKSPACE", _DEFAULT_WORKSPACE))
_gates = ConfirmationGateRegistry()


def _confirm_via_cli(gate) -> bool:
    return click.confirm(f"[confirmation gate] {gate.action}: {gate.detail} -- approve?")


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


@mcp.tool()
def delete_file(path: str) -> dict:
    """Delete PATH inside the workspace. Irreversible -- gated (docs/security.md Face 3)."""
    _gates.request(
        action="delete_file",
        detail=f"delete {path!r} in workspace {_workspace}",
        confirm=_confirm_via_cli,
    )
    ops.delete_file(_workspace, path)
    return {"deleted": path}


if __name__ == "__main__":
    mcp.run()
