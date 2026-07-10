import io

from rich.console import Console

from orchestrator.report import print_run_report
from orchestrator.telemetry import RunLog, StepLog


def test_print_run_report_renders_steps_and_summary():
    run_log = RunLog()
    run_log.add(
        StepLog(
            task_id="t1",
            goal="scaffold routes",
            tier=2,
            endpoint_id="gemma-coder",
            tokens=120,
            cost=0.2,
            confidence=0.9,
            escalated=False,
            passed=True,
        )
    )
    run_log.add(
        StepLog(
            task_id="t2",
            goal="fix token expiry bug",
            tier=3,
            endpoint_id="frontier",
            tokens=340,
            cost=3.0,
            confidence=0.95,
            escalated=True,
            passed=True,
        )
    )
    summary = run_log.summary(largest_registered_cost=3.0)

    buffer = io.StringIO()
    console = Console(file=buffer, width=200)

    print_run_report(run_log, summary, console=console)

    output = buffer.getvalue()
    assert "scaffold routes" in output
    assert "gemma-coder" in output
    assert "fix token expiry bug" in output
    assert "frontier" in output
    assert "Savings" in output
    assert "6.00" in output  # baseline cost: 2 steps * 3.0
