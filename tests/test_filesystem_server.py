import pytest

from orchestrator.security.gates import ConfirmationGateRegistry, GateDeniedError
from orchestrator.servers.filesystem import server


@pytest.fixture(autouse=True)
def _fresh_gate_registry(monkeypatch):
    monkeypatch.setattr(server, "_gates", ConfirmationGateRegistry())


def test_delete_file_approved_removes_file(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "_workspace", tmp_path)
    monkeypatch.setattr(server, "_confirm_via_cli", lambda gate: True)
    target = tmp_path / "secret.txt"
    target.write_text("shh")

    result = server.delete_file("secret.txt")

    assert result == {"deleted": "secret.txt"}
    assert not target.exists()


def test_delete_file_denied_raises_and_keeps_file(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "_workspace", tmp_path)
    monkeypatch.setattr(server, "_confirm_via_cli", lambda gate: False)
    target = tmp_path / "secret.txt"
    target.write_text("shh")

    with pytest.raises(GateDeniedError):
        server.delete_file("secret.txt")

    assert target.exists()


def test_delete_file_records_gate_history(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "_workspace", tmp_path)
    monkeypatch.setattr(server, "_confirm_via_cli", lambda gate: True)
    (tmp_path / "secret.txt").write_text("shh")

    server.delete_file("secret.txt")

    history = server._gates.history()
    assert len(history) == 1
    assert history[0].action == "delete_file"
    assert history[0].decision.value == "approved"
