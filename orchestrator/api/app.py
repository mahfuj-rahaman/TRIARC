"""Management API (architecture.md #8; roadmap Phase 4): REST + a polling websocket
over run state, per-step telemetry, the model registry, and confirmation gates.

It is not a sixth model role. It performs no routing, gating, or cost decisions of its
own -- every route reads RunManager/registry/gate state or forwards a mutation into
one of them, never decides anything itself (architecture.md #9 invariant). The web
(ui/web/) and TUI (ui/tui/) clients are both thin callers of this one API.
"""

from __future__ import annotations

import asyncio
import os

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware

from orchestrator.api.run_manager import RunManager, RunNotFoundError, RunState, TERMINAL_STATUSES
from orchestrator.api.schemas import (
    CostSummaryOut,
    GateOut,
    ModelEndpointUpdate,
    ResolveGateRequest,
    RoutedStepOut,
    RunOut,
    RunSummaryOut,
    StartRunRequest,
    StepLogOut,
    StepOutcomeOut,
)
from orchestrator.registry import ModelEndpoint, ModelRegistry
from orchestrator.security.egress import read_redaction_log
from orchestrator.security.gates import ConfirmationGate
from orchestrator.tier1_client import Tier1Client

_DEFAULT_MODELS_CONFIG = "configs/models.yaml"
_DEFAULT_WORKSPACE = "."
_DEFAULT_REDACTION_LOG = ".triarc/redaction.log"
_TIER1_MODEL_ID = "local-router"
_WS_POLL_INTERVAL_SECONDS = 0.3


def _to_summary(state: RunState) -> RunSummaryOut:
    return RunSummaryOut(run_id=state.run_id, goal=state.goal, status=state.status.value)


def _to_run_out(state: RunState, registry: ModelRegistry) -> RunOut:
    cost_summary = None
    if state.run_log.steps:
        largest_cost = max((endpoint.cost for endpoint in registry.models), default=0.0)
        summary = state.run_log.summary(largest_cost)
        cost_summary = CostSummaryOut(
            step_count=summary.step_count,
            escalated_count=summary.escalated_count,
            actual_cost=summary.actual_cost,
            baseline_cost=summary.baseline_cost,
            savings=summary.savings,
        )

    return RunOut(
        run_id=state.run_id,
        goal=state.goal,
        status=state.status.value,
        routed_steps=[
            RoutedStepOut(endpoint_id=step.endpoint.id, task=step.task) for step in state.routed_steps
        ],
        outcomes=[
            StepOutcomeOut(
                task_id=outcome.task_id,
                attempts=outcome.attempts,
                passed=outcome.passed,
                escalations=outcome.escalations,
            )
            for outcome in state.outcomes
        ],
        telemetry=[
            StepLogOut(
                task_id=log.task_id,
                goal=log.goal,
                tier=log.tier,
                endpoint_id=log.endpoint_id,
                tokens=log.tokens,
                cost=log.cost,
                confidence=log.confidence,
                escalated=log.escalated,
                passed=log.passed,
            )
            for log in state.run_log.steps
        ],
        cost_summary=cost_summary,
        error=state.error,
    )


def _to_gate_out(gate: ConfirmationGate) -> GateOut:
    return GateOut(gate_id=gate.gate_id, action=gate.action, detail=gate.detail, decision=gate.decision.value)


def _default_manager() -> RunManager:
    config_path = os.environ.get("MODELS_CONFIG", _DEFAULT_MODELS_CONFIG)
    registry = ModelRegistry.load(config_path)
    tier1_endpoint = registry.get(_TIER1_MODEL_ID)
    tier1 = Tier1Client(endpoint=tier1_endpoint.endpoint, model=tier1_endpoint.model or "tier1-router")
    workspace = os.environ.get("TRIARC_WORKSPACE", _DEFAULT_WORKSPACE)
    return RunManager(registry, tier1, workspace)


def create_app(manager: RunManager | None = None) -> FastAPI:
    manager = manager or _default_manager()

    app = FastAPI(title="TRIARC management API")
    app.state.manager = manager

    # Local hackathon tool, not a public service -- the web/TUI clients run on a
    # different origin/port than this API, so allow any origin rather than pinning
    # one dev-server port.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.post("/runs", status_code=202)
    def start_run(request: StartRunRequest) -> RunSummaryOut:
        return _to_summary(manager.start_run(request.goal))

    @app.get("/runs")
    def list_runs() -> list[RunSummaryOut]:
        return [_to_summary(state) for state in manager.list_runs()]

    @app.get("/runs/{run_id}")
    def get_run(run_id: str) -> RunOut:
        try:
            state = manager.get_run(run_id)
        except RunNotFoundError:
            raise HTTPException(status_code=404, detail=f"run {run_id!r} not found") from None
        return _to_run_out(state, manager.registry)

    @app.post("/runs/{run_id}/cancel")
    def cancel_run(run_id: str) -> RunSummaryOut:
        try:
            state = manager.cancel_run(run_id)
        except RunNotFoundError:
            raise HTTPException(status_code=404, detail=f"run {run_id!r} not found") from None
        return _to_summary(state)

    @app.websocket("/runs/{run_id}/ws")
    async def run_ws(websocket: WebSocket, run_id: str) -> None:
        await websocket.accept()
        try:
            while True:
                try:
                    state = manager.get_run(run_id)
                except RunNotFoundError:
                    await websocket.close(code=4404)
                    return
                await websocket.send_json(jsonable_encoder(_to_run_out(state, manager.registry)))
                if state.status in TERMINAL_STATUSES:
                    break
                await asyncio.sleep(_WS_POLL_INTERVAL_SECONDS)
            await websocket.close()
        except WebSocketDisconnect:
            return

    @app.get("/registry")
    def get_registry() -> list[ModelEndpoint]:
        return manager.registry.models

    @app.put("/registry/{model_id}")
    def update_registry_entry(model_id: str, update: ModelEndpointUpdate) -> ModelEndpoint:
        updates = update.model_dump(exclude_none=True)
        try:
            return manager.update_endpoint(model_id, **updates)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"model {model_id!r} not found") from None

    @app.get("/gates")
    def list_gates() -> list[GateOut]:
        return [_to_gate_out(gate) for gate in manager.gates.history()]

    @app.post("/gates/{gate_id}/resolve")
    def resolve_gate(gate_id: str, request: ResolveGateRequest) -> GateOut:
        try:
            gate = manager.gates.resolve(gate_id, approved=request.approved)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"gate {gate_id!r} not found") from None
        return _to_gate_out(gate)

    @app.get("/redaction-log")
    def get_redaction_log() -> list[dict]:
        log_path = os.environ.get("TRIARC_REDACTION_LOG", _DEFAULT_REDACTION_LOG)
        return read_redaction_log(log_path)

    return app
