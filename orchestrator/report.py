"""Terminal run report (roadmap Phase 3 item 3): the per-step telemetry table and the
actual-vs-baseline cost summary, rendered as the demo's money-shot visual.
"""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

from orchestrator.telemetry import RunLog, RunSummary


def build_step_table(run_log: RunLog) -> Table:
    table = Table(title="TRIARC run -- per-step routing")
    table.add_column("Task", overflow="ellipsis", no_wrap=True, max_width=40)
    table.add_column("Tier")
    table.add_column("Endpoint", overflow="ellipsis", no_wrap=True, max_width=20)
    table.add_column("Tokens", justify="right")
    table.add_column("Cost", justify="right")
    table.add_column("Confidence", justify="right")
    table.add_column("Escalated")
    table.add_column("Passed")

    for step in run_log.steps:
        table.add_row(
            step.goal,
            str(step.tier) if step.tier is not None else "-",
            step.endpoint_id,
            str(step.tokens),
            f"{step.cost:.2f}",
            f"{step.confidence:.2f}",
            "yes" if step.escalated else "no",
            "-" if step.passed is None else ("yes" if step.passed else "no"),
        )
    return table


def build_summary_table(summary: RunSummary) -> Table:
    table = Table(title="Cost summary: actual vs all-frontier baseline")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    table.add_row("Steps", str(summary.step_count))
    table.add_row("Escalated steps", str(summary.escalated_count))
    table.add_row("Actual cost", f"{summary.actual_cost:.2f}")
    table.add_row("Baseline cost (all-frontier)", f"{summary.baseline_cost:.2f}")
    table.add_row("Savings", f"{summary.savings:.2f}")
    return table


def print_run_report(run_log: RunLog, summary: RunSummary, *, console: Console | None = None) -> None:
    console = console or Console()
    console.print(build_step_table(run_log))
    console.print(build_summary_table(summary))
