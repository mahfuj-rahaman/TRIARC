from pathlib import Path

from orchestrator.develop_loop import run_plan, run_step
from orchestrator.planner import RoutedStep
from orchestrator.registry import ModelEndpoint, ModelRegistry
from orchestrator.schema import Capability, Constraints, Privacy, Task
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


def _endpoint(endpoint_id: str = "gemma-coder", capabilities=(Capability.CODE_SIMPLE,)) -> ModelEndpoint:
    return ModelEndpoint(
        id=endpoint_id,
        endpoint=f"https://fireworks.test/{endpoint_id}",
        capabilities=list(capabilities),
        cost=0.2,
        privacy=Privacy.CLOUD_OK,
    )


def _install_stub_workers(monkeypatch, workers_by_endpoint_id: dict[str, _StubWorker]) -> None:
    monkeypatch.setattr(
        "orchestrator.develop_loop.WorkerClient.from_endpoint",
        lambda endpoint: workers_by_endpoint_id[endpoint.id],
    )


def test_run_step_passes_on_first_attempt(tmp_path, monkeypatch):
    task = _task()
    produced = task.model_copy(update={"result": "print(1)", "confidence": 0.9})
    _install_stub_workers(monkeypatch, {"gemma-coder": _StubWorker([produced])})
    sandbox = _StubSandbox(tmp_path, [SandboxResult(exit_code=0, stdout="1 passed", stderr="")])

    outcome = run_step(RoutedStep(task=task, endpoint=_endpoint()), ModelRegistry(models=[]), sandbox)

    assert outcome.passed is True
    assert outcome.attempts == 1
    assert outcome.escalations == []
    assert (tmp_path / "out.py").read_text() == "print(1)"


def test_run_step_retries_with_feedback_and_then_passes(tmp_path, monkeypatch):
    task = _task()
    first = task.model_copy(update={"result": "broken", "confidence": 0.9})
    second = task.model_copy(update={"result": "fixed", "confidence": 0.9})
    worker = _StubWorker([first, second])
    _install_stub_workers(monkeypatch, {"gemma-coder": worker})
    sandbox = _StubSandbox(
        tmp_path,
        [
            SandboxResult(exit_code=1, stdout="", stderr="AssertionError"),
            SandboxResult(exit_code=0, stdout="1 passed", stderr=""),
        ],
    )

    outcome = run_step(RoutedStep(task=task, endpoint=_endpoint()), ModelRegistry(models=[]), sandbox)

    assert outcome.passed is True
    assert outcome.attempts == 2
    assert (tmp_path / "out.py").read_text() == "fixed"
    assert "AssertionError" in worker.calls[1][1]
    assert '<untrusted-data source="code-sandbox">' in worker.calls[1][1]


def test_run_step_exhausts_attempts_and_reports_failure(tmp_path, monkeypatch):
    task = _task()
    produced = task.model_copy(update={"result": "still broken", "confidence": 0.9})
    worker = _StubWorker([produced, produced, produced])
    _install_stub_workers(monkeypatch, {"gemma-coder": worker})
    failing = SandboxResult(exit_code=1, stdout="", stderr="still failing")
    sandbox = _StubSandbox(tmp_path, [failing, failing, failing])

    outcome = run_step(
        RoutedStep(task=task, endpoint=_endpoint()), ModelRegistry(models=[]), sandbox, max_attempts=3
    )

    assert outcome.passed is False
    assert outcome.attempts == 3
    assert outcome.sandbox_result.stderr == "still failing"
    assert len(worker.calls) == 3


def test_run_step_skips_write_when_no_context_refs(tmp_path, monkeypatch):
    task = _task(context_refs=())
    produced = task.model_copy(update={"result": "print(1)", "confidence": 0.9})
    _install_stub_workers(monkeypatch, {"gemma-coder": _StubWorker([produced])})
    sandbox = _StubSandbox(tmp_path, [SandboxResult(exit_code=0, stdout="ok", stderr="")])

    outcome = run_step(RoutedStep(task=task, endpoint=_endpoint()), ModelRegistry(models=[]), sandbox)

    assert outcome.passed is True
    assert list(tmp_path.iterdir()) == []


def test_run_step_escalates_on_low_confidence_then_passes(tmp_path, monkeypatch):
    weak = _endpoint("weak", capabilities=[Capability.CODE_SIMPLE])
    strong = _endpoint("strong", capabilities=[Capability.TOOL_USE])
    registry = ModelRegistry(models=[weak, strong])

    task = Task(
        goal="do something uncertain",
        capability_required=Capability.CODE_SIMPLE,
        context_refs=["out.py"],
        constraints=Constraints(privacy=Privacy.CLOUD_OK),
    )
    low_confidence = task.model_copy(update={"confidence": 0.2})
    high_confidence = task.model_copy(
        update={"capability_required": Capability.TOOL_USE, "confidence": 0.9, "result": "print(1)"}
    )
    _install_stub_workers(
        monkeypatch, {"weak": _StubWorker([low_confidence]), "strong": _StubWorker([high_confidence])}
    )
    sandbox = _StubSandbox(tmp_path, [SandboxResult(exit_code=0, stdout="ok", stderr="")])

    outcome = run_step(RoutedStep(task=task, endpoint=weak), registry, sandbox)

    assert outcome.passed is True
    assert outcome.attempts == 2
    assert outcome.escalations == ["low confidence (0.2)"]
    assert (tmp_path / "out.py").read_text() == "print(1)"


def test_run_step_escalates_on_explicit_escalation_reason(tmp_path, monkeypatch):
    weak = _endpoint("weak", capabilities=[Capability.CODE_SIMPLE])
    strong = _endpoint("strong", capabilities=[Capability.TOOL_USE])
    registry = ModelRegistry(models=[weak, strong])

    task = Task(
        goal="do something tricky",
        capability_required=Capability.CODE_SIMPLE,
        context_refs=["out.py"],
        constraints=Constraints(privacy=Privacy.CLOUD_OK),
    )
    needs_help = task.model_copy(
        update={"confidence": 0.95, "escalation_reason": "requires cross-file reasoning"}
    )
    fixed = task.model_copy(
        update={"capability_required": Capability.TOOL_USE, "confidence": 0.9, "result": "print(1)"}
    )
    _install_stub_workers(
        monkeypatch, {"weak": _StubWorker([needs_help]), "strong": _StubWorker([fixed])}
    )
    sandbox = _StubSandbox(tmp_path, [SandboxResult(exit_code=0, stdout="ok", stderr="")])

    outcome = run_step(RoutedStep(task=task, endpoint=weak), registry, sandbox)

    assert outcome.passed is True
    assert outcome.escalations == ["requires cross-file reasoning"]


def test_run_step_proceeds_when_escalation_ladder_is_exhausted(tmp_path, monkeypatch):
    endpoint = _endpoint("frontier", capabilities=[Capability.RESEARCH])
    registry = ModelRegistry(models=[endpoint])

    task = Task(
        goal="do the impossible",
        capability_required=Capability.RESEARCH,
        constraints=Constraints(privacy=Privacy.CLOUD_OK),
    )
    still_uncertain = task.model_copy(update={"confidence": 0.1})
    _install_stub_workers(monkeypatch, {"frontier": _StubWorker([still_uncertain])})
    sandbox = _StubSandbox(tmp_path, [SandboxResult(exit_code=1, stdout="", stderr="fail")])

    outcome = run_step(RoutedStep(task=task, endpoint=endpoint), registry, sandbox, max_attempts=1)

    assert outcome.passed is False
    assert outcome.escalations == []


def test_run_plan_stops_at_first_failing_step(tmp_path, monkeypatch):
    endpoint = _endpoint()
    step_a = RoutedStep(task=_task(context_refs=["a.py"]), endpoint=endpoint)
    step_b = RoutedStep(task=_task(context_refs=["b.py"]), endpoint=endpoint)

    a_result = step_a.task.model_copy(update={"result": "print('a')", "confidence": 0.9})
    b_result = step_b.task.model_copy(update={"result": "broken", "confidence": 0.9})
    _install_stub_workers(
        monkeypatch, {"gemma-coder": _StubWorker([a_result, b_result, b_result, b_result])}
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

    outcomes = run_plan([step_a, step_b], ModelRegistry(models=[]), sandbox, max_attempts=3)

    assert [o.passed for o in outcomes] == [True, False]
    assert len(sandbox.run_calls) == 4
