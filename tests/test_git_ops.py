import subprocess
from pathlib import Path

from orchestrator.servers.git import ops


def _git(path: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(path), capture_output=True, text=True
    )


def _init_repo(path: Path) -> None:
    _git(path, "init")
    _git(path, "config", "user.email", "test@example.com")
    _git(path, "config", "user.name", "Test")


def test_commit_stages_and_commits_all_changes_by_default(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "file.txt").write_text("hello")

    result = ops.commit(tmp_path, "add file")

    assert result["exit_code"] == 0
    log = _git(tmp_path, "log", "--oneline")
    assert "add file" in log.stdout


def test_commit_scoped_to_paths_ignores_other_changes(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "a.txt").write_text("a")
    (tmp_path / "b.txt").write_text("b")

    result = ops.commit(tmp_path, "add a only", paths=["a.txt"])

    assert result["exit_code"] == 0
    status = _git(tmp_path, "status", "--porcelain")
    assert "b.txt" in status.stdout
    assert "a.txt" not in status.stdout


def test_diff_reports_uncommitted_changes(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "file.txt").write_text("hello")
    ops.commit(tmp_path, "init")
    (tmp_path / "file.txt").write_text("hello world")

    result = ops.diff(tmp_path)

    assert "file.txt" in result["stdout"]


def test_branch_creates_and_switches(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "file.txt").write_text("hello")
    ops.commit(tmp_path, "init")

    result = ops.branch(tmp_path, "feature-x")

    assert result["exit_code"] == 0
    current = _git(tmp_path, "branch", "--show-current")
    assert current.stdout.strip() == "feature-x"


def test_clone_into_workspace(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    _init_repo(source)
    (source / "file.txt").write_text("hello")
    ops.commit(source, "init")

    dest_parent = tmp_path / "dest_parent"
    dest_parent.mkdir()
    result = ops.clone(dest_parent, str(source), "cloned")

    assert result["exit_code"] == 0
    assert (dest_parent / "cloned" / "file.txt").exists()
