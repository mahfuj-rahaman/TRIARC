"""TRIARC CLI entry point (README quickstart: `triarc run "<goal>"`)."""

from __future__ import annotations

import json
import os

import click

from orchestrator.develop_loop import run_plan
from orchestrator.planner import route_plan
from orchestrator.registry import ModelRegistry
from orchestrator.servers.code_sandbox.runtime import ContainerRuntime
from orchestrator.tier1_client import Tier1Client

_DEFAULT_MODELS_CONFIG = "configs/models.yaml"
_DEFAULT_WORKSPACE = "."
_TIER1_MODEL_ID = "local-router"


@click.group()
def cli() -> None:
    """TRIARC -- routes before it reasons."""


@cli.command()
@click.argument("goal")
@click.option(
    "--execute/--no-execute",
    default=False,
    help="Run the test-run-read-fix loop after routing "
    "(requires Docker and live Tier 2/3 endpoints).",
)
def run(goal: str, execute: bool) -> None:
    """Decompose GOAL into a routed plan and echo each step's resolved endpoint."""
    config_path = os.environ.get("MODELS_CONFIG", _DEFAULT_MODELS_CONFIG)
    registry = ModelRegistry.load(config_path)
    tier1 = registry.get(_TIER1_MODEL_ID)

    client = Tier1Client(endpoint=tier1.endpoint)
    routed_steps = route_plan(goal, client, registry)
    click.echo(
        json.dumps(
            [
                {"endpoint": step.endpoint.id, "task": step.task.model_dump()}
                for step in routed_steps
            ],
            indent=2,
        )
    )

    if not execute:
        return

    workspace = os.environ.get("TRIARC_WORKSPACE", _DEFAULT_WORKSPACE)
    sandbox = ContainerRuntime(workspace)
    outcomes = run_plan(routed_steps, registry, sandbox)
    click.echo(
        json.dumps(
            [
                {
                    "task_id": outcome.task_id,
                    "attempts": outcome.attempts,
                    "passed": outcome.passed,
                    "escalations": outcome.escalations,
                }
                for outcome in outcomes
            ],
            indent=2,
        )
    )


if __name__ == "__main__":
    cli()
