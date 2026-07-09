import json

from click.testing import CliRunner

from orchestrator.cli import cli
from orchestrator.schema import Capability, Plan, Task
from orchestrator.servers.code_sandbox.runtime import SandboxResult


class _FakeTier1Client:
    def __init__(self, endpoint: str) -> None:
        self.endpoint = endpoint

    def plan(self, goal: str) -> Plan:
        return Plan(
            goal=goal,
            steps=[Task(goal="classify", capability_required=Capability.ROUTE)],
        )


def _set_registry_env(monkeypatch):
    monkeypatch.setenv("LOCAL_ENDPOINT", "http://localhost:8000/v1")
    monkeypatch.setenv("FIREWORKS_GEMMA_MODEL", "gemma-test")
    monkeypatch.setenv("FIREWORKS_LARGE_MODEL", "large-test")


def test_run_echoes_routed_plan(monkeypatch):
    _set_registry_env(monkeypatch)
    monkeypatch.setattr("orchestrator.cli.Tier1Client", _FakeTier1Client)

    result = CliRunner().invoke(cli, ["run", "add JWT auth"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload[0]["endpoint"] == "local-router"
    assert payload[0]["task"]["capability_required"] == "route"


def test_run_without_execute_flag_skips_develop_loop(monkeypatch):
    _set_registry_env(monkeypatch)
    monkeypatch.setattr("orchestrator.cli.Tier1Client", _FakeTier1Client)

    result = CliRunner().invoke(cli, ["run", "add JWT auth"])

    assert result.exit_code == 0, result.output
    assert '"passed"' not in result.output


def test_run_execute_runs_develop_loop_and_reports_outcomes(monkeypatch, tmp_path):
    _set_registry_env(monkeypatch)
    monkeypatch.setenv("TRIARC_WORKSPACE", str(tmp_path))
    monkeypatch.setattr("orchestrator.cli.Tier1Client", _FakeTier1Client)

    class _StubWorker:
        def execute(self, task, feedback=None):
            return task

    monkeypatch.setattr(
        "orchestrator.develop_loop.WorkerClient.from_endpoint", lambda endpoint: _StubWorker()
    )
    monkeypatch.setattr(
        "orchestrator.servers.code_sandbox.runtime.ContainerRuntime.run",
        lambda self, command: SandboxResult(exit_code=0, stdout="1 passed", stderr=""),
    )

    result = CliRunner().invoke(cli, ["run", "add JWT auth", "--execute"])

    assert result.exit_code == 0, result.output
    assert '"passed": true' in result.output
