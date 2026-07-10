"""Per-step telemetry and the actual-vs-baseline cost summary (roadmap Phase 3;
docs/routing.md "Cost accounting"; features.md #8).

Each resolved worker call is logged as a StepLog. `cost` is the endpoint's registered
relative cost (configs/models.yaml notes it's illustrative, not real per-token
pricing), so the run summary compares actual routed cost against the cost of the same
number of steps if every one had gone to the most expensive registered endpoint.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class StepLog:
    task_id: str
    goal: str
    tier: int | None
    endpoint_id: str
    tokens: int
    cost: float
    confidence: float
    escalated: bool
    passed: bool | None = None


@dataclass
class RunSummary:
    step_count: int
    escalated_count: int
    actual_cost: float
    baseline_cost: float

    @property
    def savings(self) -> float:
        return self.baseline_cost - self.actual_cost


class RunLog:
    """Collects StepLogs for a single `triarc run` and summarizes them."""

    def __init__(self) -> None:
        self._steps: list[StepLog] = []

    def add(self, step_log: StepLog) -> None:
        self._steps.append(step_log)

    @property
    def steps(self) -> list[StepLog]:
        return list(self._steps)

    def summary(self, largest_registered_cost: float) -> RunSummary:
        actual_cost = sum(step.cost for step in self._steps)
        baseline_cost = len(self._steps) * largest_registered_cost
        return RunSummary(
            step_count=len(self._steps),
            escalated_count=sum(1 for step in self._steps if step.escalated),
            actual_cost=actual_cost,
            baseline_cost=baseline_cost,
        )
