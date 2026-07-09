from pathlib import Path

from orchestrator.develop_loop import run_plan, run_step
from orchestrator.planner import RoutedStep
from orchestrator.registry import ModelEndpoint
from orchestrator.schema import Capability, Privacy, Task
from orchestrator.servers.code_sandbox.runtime import SandboxResult


class _StubWorker:
    def __init__(self, results: list[Task]) -> None:
        self._results = results
        self.calls: list[tuple[Task, str | None]] = []

    def execute(self, task: Task, feedback: str | None = None) -> Task:
        self.calls.append((task, feedback))
        return self._results[len(self.calls) - 1]


class _StubSandbox:
    def __init__(self, workspace: Path, run_results: list[SandboxResult]) -> None:
        self.workspace = workspace
        self._run_results = run_results
        self.run_calls: list[list[str]] = []

    def run(self, command: list[str]) -> SandboxResult:
        self.run_calls.append(command)
        return self._run_results[len(self.run_calls) - 1]


def _task(context_refs=("out.py",)) -> Task:
    return Task(
        goal="write a script",
        capability_required=Capability.CODE_SIMPLE,
        context_refs=list(context_refs),
    )


def _endpoint() -> ModelEndpoint:
    return ModelEndpoint(
        id="gemma-coder",
        endpoint="https://fireworks.test/v1",
        capabilities=[Capability.CODE_SIMPLE],
        cost=0.2,
        privacy=Privacy.CLOUD_OK,
    )


def test_run_step_passes_on_first_attempt(tmp_path):
    task = _task()
    produced = task.model_copy(update={"result": "print(1)"})
    worker = _StubWorker([produced])
    sandbox = _StubSandbox(tmp_path, [SandboxResult(exit_code=0, stdout="1 passed", stderr="")])

    outcome = run_step(RoutedStep(task=task, endpoint=_endpoint()), worker, sandbox)

    assert outcome.passed is True
    assert outcome.attempts == 1
    assert (tmp_path / "out.py").read_text() == "print(1)"
    assert len(worker.calls) == 1
    assert worker.calls[0][1] is None


def test_run_step_retries_with_feedback_and_then_passes(tmp_path):
    task = _task()
    first = task.model_copy(update={"result": "broken"})
    second = task.model_copy(update={"result": "fixed"})
    worker = _StubWorker([first, second])
    sandbox = _StubSandbox(
        tmp_path,
        [
            SandboxResult(exit_code=1, stdout="", stderr="AssertionError"),
            SandboxResult(exit_code=0, stdout="1 passed", stderr=""),
        ],
    )

    outcome = run_step(RoutedStep(task=task, endpoint=_endpoint()), worker, sandbox)

    assert outcome.passed is True
    assert outcome.attempts == 2
    assert (tmp_path / "out.py").read_text() == "fixed"
    assert "AssertionError" in worker.calls[1][1]


def test_run_step_exhausts_attempts_and_reports_failure(tmp_path):
    task = _task()
    produced = task.model_copy(update={"result": "still broken"})
    worker = _StubWorker([produced, produced, produced])
    failing = SandboxResult(exit_code=1, stdout="", stderr="still failing")
    sandbox = _StubSandbox(tmp_path, [failing, failing, failing])

    outcome = run_step(RoutedStep(task=task, endpoint=_endpoint()), worker, sandbox, max_attempts=3)

    assert outcome.passed is False
    assert outcome.attempts == 3
    assert outcome.sandbox_result.stderr == "still failing"
    assert len(worker.calls) == 3


def test_run_step_skips_write_when_no_context_refs(tmp_path):
    task = _task(context_refs=())
    produced = task.model_copy(update={"result": "print(1)"})
    worker = _StubWorker([produced])
    sandbox = _StubSandbox(tmp_path, [SandboxResult(exit_code=0, stdout="ok", stderr="")])

    outcome = run_step(RoutedStep(task=task, endpoint=_endpoint()), worker, sandbox)

    assert outcome.passed is True
    assert list(tmp_path.iterdir()) == []


def test_run_plan_stops_at_first_failing_step(tmp_path, monkeypatch):
    endpoint = _endpoint()
    step_a = RoutedStep(task=_task(context_refs=["a.py"]), endpoint=endpoint)
    step_b = RoutedStep(task=_task(context_refs=["b.py"]), endpoint=endpoint)

    workers = iter(
        [
            _StubWorker([step_a.task.model_copy(update={"result": "print('a')"})]),
            _StubWorker([step_b.task.model_copy(update={"result": "broken"})] * 3),
        ]
    )
    monkeypatch.setattr(
        "orchestrator.develop_loop.WorkerClient.from_endpoint", lambda endpoint: next(workers)
    )
    sandbox = _StubSandbox(
        tmp_path,
        [
            SandboxResult(exit_code=0, stdout="ok", stderr=""),
            SandboxResult(exit_code=1, stdout="", stderr="fail"),
            SandboxResult(exit_code=1, stdout="", stderr="fail"),
            SandboxResult(exit_code=1, stdout="", stderr="fail"),
        ],
    )

    outcomes = run_plan([step_a, step_b], sandbox, max_attempts=3)

    assert [o.passed for o in outcomes] == [True, False]
    assert len(sandbox.run_calls) == 4
