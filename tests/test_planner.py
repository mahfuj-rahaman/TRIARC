from orchestrator.planner import route_plan
from orchestrator.registry import ModelEndpoint, ModelRegistry
from orchestrator.schema import Capability, Constraints, Plan, Privacy, Task


class _StubTier1Client:
    def __init__(self, plan: Plan) -> None:
        self._plan = plan
        self.last_goal: str | None = None

    def plan(self, goal: str) -> Plan:
        self.last_goal = goal
        return self._plan


def test_route_plan_resolves_each_step_to_an_endpoint():
    registry = ModelRegistry(
        models=[
            ModelEndpoint(
                id="local-router",
                endpoint="http://local:8000/v1",
                capabilities=[Capability.ROUTE, Capability.CODE_SIMPLE],
                cost=0,
                privacy=Privacy.LOCAL,
            ),
            ModelEndpoint(
                id="gemma-coder",
                endpoint="https://fireworks.test/v1",
                capabilities=[Capability.CODE_COMPLEX],
                cost=0.2,
                privacy=Privacy.CLOUD_OK,
            ),
        ]
    )
    plan = Plan(
        goal="add JWT auth",
        steps=[
            Task(
                goal="scaffold routes",
                capability_required=Capability.CODE_COMPLEX,
                constraints=Constraints(privacy=Privacy.CLOUD_OK),
            ),
            Task(goal="classify request", capability_required=Capability.ROUTE),
        ],
    )
    tier1 = _StubTier1Client(plan)

    routed = route_plan("add JWT auth", tier1, registry)

    assert tier1.last_goal == "add JWT auth"
    assert [step.endpoint.id for step in routed] == ["gemma-coder", "local-router"]
    assert [step.task.goal for step in routed] == ["scaffold routes", "classify request"]
