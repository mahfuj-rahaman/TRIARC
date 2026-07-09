"""Rootless, workspace-scoped code execution container (docs/security.md, "Code sandbox").

Wraps `docker run` via an injectable command runner so tests don't need a live Docker
daemon. Every run is: no network by default (per-call opt-in), a non-root user, a
read-only root filesystem with only the workspace mounted read-write, resource limits,
and a hard timeout.
"""

from __future__ import annotations

import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

_IMAGE = "python:3.12-slim"
_SANDBOX_USER = "65534:65534"  # nobody -- rootless inside the container
_DEFAULT_TIMEOUT_SECONDS = 30
_DEFAULT_MEMORY = "512m"
_DEFAULT_CPUS = "1"
_DEFAULT_PIDS_LIMIT = "128"

CommandRunner = Callable[..., subprocess.CompletedProcess]


@dataclass
class SandboxResult:
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False


class ContainerRuntime:
    """Runs commands inside a rootless, network-isolated, workspace-scoped container."""

    def __init__(
        self,
        workspace: str | Path,
        *,
        timeout_seconds: int = _DEFAULT_TIMEOUT_SECONDS,
        memory: str = _DEFAULT_MEMORY,
        cpus: str = _DEFAULT_CPUS,
        pids_limit: str = _DEFAULT_PIDS_LIMIT,
        runner: CommandRunner = subprocess.run,
    ) -> None:
        self._workspace = Path(workspace)
        self._timeout_seconds = timeout_seconds
        self._memory = memory
        self._cpus = cpus
        self._pids_limit = pids_limit
        self._runner = runner

    @property
    def workspace(self) -> Path:
        return self._workspace

    def run(self, command: list[str], *, allow_network: bool = False) -> SandboxResult:
        """Run COMMAND inside the container, with the workspace mounted at /workspace."""
        container_name = f"triarc-sandbox-{uuid.uuid4().hex}"
        args = [
            "docker", "run", "--rm",
            "--name", container_name,
            "--user", _SANDBOX_USER,
            "--read-only",
            "--security-opt", "no-new-privileges",
            "--network", "bridge" if allow_network else "none",
            "--memory", self._memory,
            "--cpus", self._cpus,
            "--pids-limit", self._pids_limit,
            "-v", f"{self._workspace}:/workspace:rw",
            "-w", "/workspace",
            _IMAGE,
            *command,
        ]

        try:
            completed = self._runner(
                args, capture_output=True, text=True, timeout=self._timeout_seconds
            )
        except subprocess.TimeoutExpired:
            self._runner(["docker", "kill", container_name], capture_output=True, text=True)
            return SandboxResult(
                exit_code=-1, stdout="", stderr="sandbox execution timed out", timed_out=True
            )

        return SandboxResult(
            exit_code=completed.returncode, stdout=completed.stdout, stderr=completed.stderr
        )

    def run_code(self, code: str, *, filename: str = "main.py", allow_network: bool = False) -> SandboxResult:
        """Write CODE into the workspace as FILENAME and run it with python."""
        source_path = self._workspace / filename
        source_path.write_text(code)
        try:
            return self.run(["python", filename], allow_network=allow_network)
        finally:
            source_path.unlink(missing_ok=True)
