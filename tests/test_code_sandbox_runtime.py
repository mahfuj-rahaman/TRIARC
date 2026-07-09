import subprocess

from orchestrator.servers.code_sandbox.runtime import ContainerRuntime


class _FakeRunner:
    def __init__(self, completed: subprocess.CompletedProcess | None = None, timeout_on_call: int | None = None):
        self.calls: list[tuple[list[str], dict]] = []
        self._completed = completed or subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        self._timeout_on_call = timeout_on_call

    def __call__(self, args, **kwargs):
        self.calls.append((args, kwargs))
        if self._timeout_on_call == len(self.calls):
            raise subprocess.TimeoutExpired(cmd=args, timeout=kwargs.get("timeout"))
        return self._completed


def test_run_defaults_to_no_network(tmp_path):
    runner = _FakeRunner()
    runtime = ContainerRuntime(tmp_path, runner=runner)

    runtime.run(["python", "-c", "print(1)"])

    args, kwargs = runner.calls[0]
    assert "--network" in args
    assert args[args.index("--network") + 1] == "none"
    assert kwargs["timeout"] == 30


def test_run_allow_network_uses_bridge(tmp_path):
    runner = _FakeRunner()
    runtime = ContainerRuntime(tmp_path, runner=runner)

    runtime.run(["python", "-c", "print(1)"], allow_network=True)

    args, _ = runner.calls[0]
    assert args[args.index("--network") + 1] == "bridge"


def test_run_mounts_workspace_readwrite_and_scopes_user(tmp_path):
    runner = _FakeRunner()
    runtime = ContainerRuntime(tmp_path, runner=runner)

    runtime.run(["true"])

    args, _ = runner.calls[0]
    assert f"{tmp_path}:/workspace:rw" in args
    assert "--user" in args
    assert args[args.index("--user") + 1] == "65534:65534"
    assert "--read-only" in args


def test_run_returns_completed_process_output(tmp_path):
    completed = subprocess.CompletedProcess(args=[], returncode=1, stdout="out", stderr="err")
    runner = _FakeRunner(completed=completed)
    runtime = ContainerRuntime(tmp_path, runner=runner)

    result = runtime.run(["false"])

    assert result.exit_code == 1
    assert result.stdout == "out"
    assert result.stderr == "err"
    assert result.timed_out is False


def test_run_kills_container_and_reports_timeout(tmp_path):
    runner = _FakeRunner(timeout_on_call=1)
    runtime = ContainerRuntime(tmp_path, runner=runner)

    result = runtime.run(["sleep", "999"])

    assert result.timed_out is True
    assert result.exit_code == -1
    assert len(runner.calls) == 2
    kill_args, _ = runner.calls[1]
    assert kill_args[:2] == ["docker", "kill"]


def test_run_code_writes_and_cleans_up_source_file(tmp_path):
    runner = _FakeRunner()
    runtime = ContainerRuntime(tmp_path, runner=runner)

    runtime.run_code("print('hi')", filename="script.py")

    args, _ = runner.calls[0]
    assert "python" in args
    assert "script.py" in args
    assert not (tmp_path / "script.py").exists()
