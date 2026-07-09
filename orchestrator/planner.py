"""Router/planner loop: goal -> plan -> per-step endpoint resolution (architecture.md #4).

Decomposes a goal into an ordered plan via the Tier-1 client, then resolves each step's
capability_required to a concrete endpoint through the registry. Worker invocation and
result assembly are the test-run-read-fix loop (roadmap Phase 1 item 5).
"""

from __future__ import annotations

from dataclasses import dataclass

from orchestrator.registry import ModelEndpoint, ModelRegistry
from orchestrator.schema import Task
from orchestrator.tier1_client import Tier1Client


@dataclass
class RoutedStep:
    task: Task
    endpoint: ModelEndpoint


def route_plan(goal: str, tier1: Tier1Client, registry: ModelRegistry) -> list[RoutedStep]:
    """Decompose GOAL into a plan and resolve each step to a concrete endpoint."""
    plan = tier1.plan(goal)
    return [
        RoutedStep(
            task=step,
            endpoint=registry.resolve(step.capability_required, step.constraints),
        )
        for step in plan.steps
    ]
