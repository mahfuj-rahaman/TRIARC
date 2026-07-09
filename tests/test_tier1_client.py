import json

from orchestrator.schema import Capability
from orchestrator.tier1_client import Tier1Client
from tests._openai_fakes import install_fake_openai


def test_route_returns_classified_task(monkeypatch):
    content = json.dumps({"capability_required": "code_complex", "confidence": 0.8})
    fake = install_fake_openai(monkeypatch, "orchestrator.tier1_client", content)

    client = Tier1Client(endpoint="http://local:8000/v1")
    task = client.route("add JWT auth")

    assert task.goal == "add JWT auth"
    assert task.capability_required == Capability.CODE_COMPLEX
    assert task.confidence == 0.8
    assert fake.chat.completions.last_kwargs["response_format"]["json_schema"]["name"] == "task"


def test_plan_returns_ordered_steps(monkeypatch):
    content = json.dumps(
        {
            "steps": [
                {"goal": "write routes", "capability_required": "code_complex"},
                {"goal": "write tests", "capability_required": "code_complex"},
            ]
        }
    )
    fake = install_fake_openai(monkeypatch, "orchestrator.tier1_client", content)

    client = Tier1Client(endpoint="http://local:8000/v1")
    plan = client.plan("add JWT auth")

    assert plan.goal == "add JWT auth"
    assert [step.goal for step in plan.steps] == ["write routes", "write tests"]
    assert all(step.capability_required == Capability.CODE_COMPLEX for step in plan.steps)
    assert fake.chat.completions.last_kwargs["response_format"]["json_schema"]["name"] == "plan"
