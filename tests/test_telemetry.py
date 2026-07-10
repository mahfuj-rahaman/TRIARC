from orchestrator.telemetry import RunLog, StepLog


def _log(cost: float, escalated: bool = False) -> StepLog:
    return StepLog(
        task_id="t1",
        goal="do something",
        tier=2,
        endpoint_id="gemma-coder",
        tokens=100,
        cost=cost,
        confidence=0.9,
        escalated=escalated,
    )


def test_run_log_summary_computes_actual_and_baseline_cost():
    run_log = RunLog()
    run_log.add(_log(0.0))
    run_log.add(_log(0.2))
    run_log.add(_log(0.2, escalated=True))

    summary = run_log.summary(largest_registered_cost=3.0)

    assert summary.step_count == 3
    assert summary.escalated_count == 1
    assert summary.actual_cost == 0.4
    assert summary.baseline_cost == 9.0
    assert summary.savings == 8.6


def test_run_log_summary_with_no_steps_is_zero():
    run_log = RunLog()

    summary = run_log.summary(largest_registered_cost=3.0)

    assert summary.step_count == 0
    assert summary.actual_cost == 0.0
    assert summary.baseline_cost == 0.0
    assert summary.savings == 0.0


def test_run_log_steps_returns_a_copy():
    run_log = RunLog()
    run_log.add(_log(0.0))

    steps = run_log.steps
    steps.append(_log(0.2))

    assert len(run_log.steps) == 1
