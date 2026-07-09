"""Test-run-read-fix loop with reactive escalation (roadmap Phase 1 item 5, Phase 2
item 1; features.md #1 steps 3-5; docs/routing.md "Escalation ladder" branch B).

For each routed step: the worker produces a file, the sandbox runs the test suite, and
on failure the loop feeds stdout/stderr -- tagged as untrusted data (docs/security.md
Face 2) -- back to the worker and retries. If a worker's own result carries low
confidence or an escalation_reason, the loop re-resolves the task's capability one rung
up the registry's ladder and retries there instead of repeating the same endpoint
(docs/routing.md "B. Reactive (fail-upward)"), carrying the reason forward as context.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from orchestrator.planner import RoutedStep
from orchestrator.registry import ModelRegistry, NoCapableEndpointError, escalate_capability
from orchestrator.schema import Task
from orchestrator.security.ingress import wrap_untrusted
from orchestrator.servers.code_sandbox.runtime import ContainerRuntime, SandboxResult
from orchestrator.servers.filesystem import ops as fs_ops
from orchestrator.worker_client import WorkerClient

_DEFAULT_MAX_ATTEMPTS = 3
_DEFAULT_TEST_COMMAND = ["python", "-m", "pytest", "-q"]
_CONFIDENCE_THRESHOLD = 0.5


@dataclass
class StepOutcome:
    task_id: str
    attempts: int
    passed: bool
    sandbox_result: SandboxResult | None
    escalations: list[str] = field(default_factory=list)


def _needs_escalation(produced: Task, confidence_threshold: float) -> bool:
    return produced.confidence < confidence_threshold or produced.escalation_reason is not None


def run_step(
    step: RoutedStep,
    registry: ModelRegistry,
    sandbox: ContainerRuntime,
    *,
    max_attempts: int = _DEFAULT_MAX_ATTEMPTS,
    test_command: list[str] | None = None,
    confidence_threshold: float = _CONFIDENCE_THRESHOLD,
) -> StepOutcome:
    """Execute STEP: write the worker's result, run tests, retry (and escalate) on failure."""
    command = test_command or _DEFAULT_TEST_COMMAND
    task = step.task
    endpoint = step.endpoint
    feedback: str | None = None
    sandbox_result: SandboxResult | None = None
    escalations: list[str] = []

    for attempt in range(1, max_attempts + 1):
        worker = WorkerClient.from_endpoint(endpoint)
        produced = worker.execute(task, feedback=feedback)

        if _needs_escalation(produced, confidence_threshold):
            reason = produced.escalation_reason or f"low confidence ({produced.confidence})"
            try:
                stronger = escalate_capability(task.capability_required)
                endpoint = registry.resolve(stronger, task.constraints)
            except NoCapableEndpointError:
                pass  # already at the ceiling, or nothing satisfies it under this task's
                # privacy constraint -- proceed with what the worker already produced.
            else:
                escalations.append(reason)
                task = task.model_copy(update={"capability_required": stronger})
                feedback = reason
                continue

        if produced.result is not None and produced.context_refs:
            fs_ops.write_file(sandbox.workspace, produced.context_refs[0], produced.result)

        sandbox_result = sandbox.run(command)
        if sandbox_result.exit_code == 0:
            return StepOutcome(
                task_id=step.task.task_id,
                attempts=attempt,
                passed=True,
                sandbox_result=sandbox_result,
                escalations=escalations,
            )

        feedback = wrap_untrusted(
            f"stdout:\n{sandbox_result.stdout}\nstderr:\n{sandbox_result.stderr}",
            source="code-sandbox",
        )

    return StepOutcome(
        task_id=step.task.task_id,
        attempts=max_attempts,
        passed=False,
        sandbox_result=sandbox_result,
        escalations=escalations,
    )


def run_plan(
    routed_steps: list[RoutedStep],
    registry: ModelRegistry,
    sandbox: ContainerRuntime,
    *,
    max_attempts: int = _DEFAULT_MAX_ATTEMPTS,
    test_command: list[str] | None = None,
) -> list[StepOutcome]:
    """Run every step in ROUTED_STEPS in order, stopping at the first that never passes."""
    outcomes = []
    for step in routed_steps:
        outcome = run_step(
            step, registry, sandbox, max_attempts=max_attempts, test_command=test_command
        )
        outcomes.append(outcome)
        if not outcome.passed:
            break
    return outcomes
