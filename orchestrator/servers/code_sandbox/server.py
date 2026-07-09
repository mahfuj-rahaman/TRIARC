"""MCP server: containerized code execution (docs/architecture.md #5, docs/security.md).

Exposes the sandbox as two MCP tools -- run_code (execute a python snippet) and
run_command (execute an arbitrary command, e.g. `pytest`) -- both scoped to a single
workspace directory, network-isolated by default.
"""

from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP

from orchestrator.servers.code_sandbox.runtime import ContainerRuntime, SandboxResult

_DEFAULT_WORKSPACE = "."

mcp = FastMCP("triarc-code-sandbox")
_runtime = ContainerRuntime(os.environ.get("TRIARC_WORKSPACE", _DEFAULT_WORKSPACE))


def _to_dict(result: SandboxResult) -> dict:
    return {
        "exit_code": result.exit_code,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "timed_out": result.timed_out,
    }


@mcp.tool()
def run_code(code: str, allow_network: bool = False) -> dict:
    """Execute a Python snippet in the sandbox and return its exit code, stdout, stderr."""
    return _to_dict(_runtime.run_code(code, allow_network=allow_network))


@mcp.tool()
def run_command(command: list[str], allow_network: bool = False) -> dict:
    """Run an arbitrary command (e.g. `["pytest", "-q"]`) in the sandbox."""
    return _to_dict(_runtime.run(command, allow_network=allow_network))


if __name__ == "__main__":
    mcp.run()
