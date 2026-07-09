"""Confirmation-gate framework for irreversible actions (docs/security.md Face 3).

Every irreversible action -- code execution outside the sandbox, file deletion,
outbound messaging, purchases -- must pass through a gate and wait for explicit
confirmation, regardless of who or what initiated the run. No tool may resolve its
own gate or reconfigure this module (architecture.md #9 invariant).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable


class GateDecision(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"


@dataclass
class ConfirmationGate:
    action: str
    detail: str
    gate_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    decision: GateDecision = GateDecision.PENDING


class GateDeniedError(RuntimeError):
    """Raised when a gated action is denied."""


ConfirmationCallback = Callable[[ConfirmationGate], bool]


class ConfirmationGateRegistry:
    """Tracks every gate opened during a run, so an operator (or the Phase 4
    confirmation-gate inbox) can inspect pending gates and their resolutions."""

    def __init__(self) -> None:
        self._gates: dict[str, ConfirmationGate] = {}

    def open_gate(self, action: str, detail: str) -> ConfirmationGate:
        gate = ConfirmationGate(action=action, detail=detail)
        self._gates[gate.gate_id] = gate
        return gate

    def resolve(self, gate_id: str, *, approved: bool) -> ConfirmationGate:
        gate = self._gates[gate_id]
        gate.decision = GateDecision.APPROVED if approved else GateDecision.DENIED
        return gate

    def request(self, action: str, detail: str, *, confirm: ConfirmationCallback) -> ConfirmationGate:
        """Open a gate, ask CONFIRM to decide, and raise GateDeniedError if refused."""
        gate = self.open_gate(action, detail)
        approved = confirm(gate)
        self.resolve(gate.gate_id, approved=approved)
        if not approved:
            raise GateDeniedError(f"{action} was denied: {detail}")
        return gate

    def pending(self) -> list[ConfirmationGate]:
        return [gate for gate in self._gates.values() if gate.decision == GateDecision.PENDING]

    def history(self) -> list[ConfirmationGate]:
        return list(self._gates.values())
