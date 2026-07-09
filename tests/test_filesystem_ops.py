import pytest

from orchestrator.servers.filesystem import ops


def test_write_then_read_round_trips(tmp_path):
    ops.write_file(tmp_path, "notes.txt", "hello")

    assert ops.read_file(tmp_path, "notes.txt") == "hello"


def test_write_creates_parent_directories(tmp_path):
    ops.write_file(tmp_path, "nested/dir/file.txt", "content")

    assert ops.read_file(tmp_path, "nested/dir/file.txt") == "content"


def test_list_dir_lists_workspace_entries(tmp_path):
    (tmp_path / "a.txt").write_text("a")
    (tmp_path / "b.txt").write_text("b")

    assert ops.list_dir(tmp_path) == ["a.txt", "b.txt"]


def test_read_file_rejects_path_escaping_workspace(tmp_path):
    outside = tmp_path.parent / "secret.txt"
    outside.write_text("nope")

    with pytest.raises(ops.PathEscapesWorkspaceError):
        ops.read_file(tmp_path, "../secret.txt")


def test_write_file_rejects_path_escaping_workspace(tmp_path):
    with pytest.raises(ops.PathEscapesWorkspaceError):
        ops.write_file(tmp_path, "../escape.txt", "nope")


def test_list_dir_rejects_path_escaping_workspace(tmp_path):
    with pytest.raises(ops.PathEscapesWorkspaceError):
        ops.list_dir(tmp_path, "..")


def test_delete_file_removes_it(tmp_path):
    ops.write_file(tmp_path, "notes.txt", "hello")

    ops.delete_file(tmp_path, "notes.txt")

    assert not (tmp_path / "notes.txt").exists()


def test_delete_file_rejects_path_escaping_workspace(tmp_path):
    outside = tmp_path.parent / "secret.txt"
    outside.write_text("nope")

    with pytest.raises(ops.PathEscapesWorkspaceError):
        ops.delete_file(tmp_path, "../secret.txt")

    assert outside.exists()
