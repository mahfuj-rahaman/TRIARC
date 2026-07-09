import pytest

from orchestrator.security.gates import ConfirmationGateRegistry, GateDecision, GateDeniedError


def test_request_approved_returns_gate_and_records_history():
    registry = ConfirmationGateRegistry()

    gate = registry.request("delete_file", "delete secrets.txt", confirm=lambda g: True)

    assert gate.decision == GateDecision.APPROVED
    assert registry.history() == [gate]
    assert registry.pending() == []


def test_request_denied_raises_and_records_denial():
    registry = ConfirmationGateRegistry()

    with pytest.raises(GateDeniedError):
        registry.request("delete_file", "delete secrets.txt", confirm=lambda g: False)

    assert registry.history()[0].decision == GateDecision.DENIED


def test_open_gate_starts_pending_until_resolved():
    registry = ConfirmationGateRegistry()

    gate = registry.open_gate("delete_file", "delete secrets.txt")

    assert gate.decision == GateDecision.PENDING
    assert registry.pending() == [gate]

    registry.resolve(gate.gate_id, approved=True)

    assert registry.pending() == []
    assert gate.decision == GateDecision.APPROVED
