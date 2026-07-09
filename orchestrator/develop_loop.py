"""Test-run-read-fix loop (roadmap Phase 1 item 5; features.md #1 steps 3-5).

For each routed step: the worker produces a file, the sandbox runs the test suite, and
on failure the loop feeds stdout/stderr back to the worker and retries, up to a fixed
attempt budget. Confidence-driven reactive escalation is Phase 2 -- this loop only
retries the same endpoint; it never re-routes to a stronger tier.
"""

from __future__ import annotations

from dataclasses import dataclass

from orchestrator.planner import RoutedStep
from orchestrator.servers.code_sandbox.runtime import ContainerRuntime, SandboxResult
from orchestrator.servers.filesystem import ops as fs_ops
from orchestrator.worker_client import WorkerClient

_DEFAULT_MAX_ATTEMPTS = 3
_DEFAULT_TEST_COMMAND = ["python", "-m", "pytest", "-q"]


@dataclass
class StepOutcome:
    task_id: str
    attempts: int
    passed: bool
    sandbox_result: SandboxResult | None


def run_step(
    step: RoutedStep,
    worker: WorkerClient,
    sandbox: ContainerRuntime,
    *,
    max_attempts: int = _DEFAULT_MAX_ATTEMPTS,
    test_command: list[str] | None = None,
) -> StepOutcome:
    """Execute STEP: write the worker's result, run tests, retry on failure."""
    command = test_command or _DEFAULT_TEST_COMMAND
    feedback: str | None = None
    sandbox_result: SandboxResult | None = None

    for attempt in range(1, max_attempts + 1):
        produced = worker.execute(step.task, feedback=feedback)
        if produced.result is not None and produced.context_refs:
            fs_ops.write_file(sandbox.workspace, produced.context_refs[0], produced.result)

        sandbox_result = sandbox.run(command)
        if sandbox_result.exit_code == 0:
            return StepOutcome(
                task_id=step.task.task_id, attempts=attempt, passed=True, sandbox_result=sandbox_result
            )

        feedback = f"stdout:\n{sandbox_result.stdout}\nstderr:\n{sandbox_result.stderr}"

    return StepOutcome(
        task_id=step.task.task_id, attempts=max_attempts, passed=False, sandbox_result=sandbox_result
    )


def run_plan(
    routed_steps: list[RoutedStep],
    sandbox: ContainerRuntime,
    *,
    max_attempts: int = _DEFAULT_MAX_ATTEMPTS,
    test_command: list[str] | None = None,
) -> list[StepOutcome]:
    """Run every step in ROUTED_STEPS in order, stopping at the first that never passes."""
    outcomes = []
    for step in routed_steps:
        worker = WorkerClient.from_endpoint(step.endpoint)
        outcome = run_step(
            step, worker, sandbox, max_attempts=max_attempts, test_command=test_command
        )
        outcomes.append(outcome)
        if not outcome.passed:
            break
    return outcomes
