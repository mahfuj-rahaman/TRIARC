"""Workspace-scoped filesystem access (docs/features.md #6, docs/architecture.md #5).

Every path is resolved against the workspace root and rejected if it would escape it --
the workspace-scoping guarantee the sandbox and security plane depend on.
"""

from __future__ import annotations

from pathlib import Path


class PathEscapesWorkspaceError(ValueError):
    pass


def _resolve(workspace: Path, path: str) -> Path:
    workspace_resolved = workspace.resolve()
    resolved = (workspace_resolved / path).resolve()
    if not resolved.is_relative_to(workspace_resolved):
        raise PathEscapesWorkspaceError(f"{path!r} escapes the workspace")
    return resolved


def read_file(workspace: Path, path: str) -> str:
    return _resolve(workspace, path).read_text()


def write_file(workspace: Path, path: str, content: str) -> None:
    target = _resolve(workspace, path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)


def list_dir(workspace: Path, path: str = ".") -> list[str]:
    target = _resolve(workspace, path)
    return sorted(entry.name for entry in target.iterdir())


def delete_file(workspace: Path, path: str) -> None:
    _resolve(workspace, path).unlink()
