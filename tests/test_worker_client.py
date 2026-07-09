import json

from orchestrator.registry import ModelEndpoint
from orchestrator.schema import Capability, Privacy, Task
from orchestrator.worker_client import WorkerClient
from tests._openai_fakes import install_fake_openai


def test_execute_returns_task_with_worker_result(monkeypatch):
    content = json.dumps({"result": "print('hello')", "confidence": 0.9})
    fake = install_fake_openai(monkeypatch, "orchestrator.worker_client", content)

    client = WorkerClient(endpoint="https://fireworks.test/v1", model="gemma")
    task = Task(
        goal="write hello world script",
        capability_required=Capability.CODE_SIMPLE,
        context_refs=["hello.py"],
    )

    produced = client.execute(task)

    assert produced.task_id == task.task_id
    assert produced.context_refs == ["hello.py"]
    assert produced.result == "print('hello')"
    assert produced.confidence == 0.9
    messages = fake.chat.completions.last_kwargs["messages"]
    assert messages[-1]["content"] == "write hello world script"


def test_execute_includes_feedback_from_previous_failed_attempt(monkeypatch):
    content = json.dumps({"result": "print('fixed')", "confidence": 0.95})
    fake = install_fake_openai(monkeypatch, "orchestrator.worker_client", content)

    client = WorkerClient(endpoint="https://fireworks.test/v1", model="gemma")
    task = Task(goal="fix the bug", capability_required=Capability.DEBUG)

    client.execute(task, feedback="AssertionError: expected 2 got 1")

    messages = fake.chat.completions.last_kwargs["messages"]
    assert "AssertionError" in messages[-1]["content"]


def test_from_endpoint_uses_endpoint_model_or_falls_back_to_id(monkeypatch):
    fake = install_fake_openai(
        monkeypatch, "orchestrator.worker_client", json.dumps({"result": "x", "confidence": 1.0})
    )

    endpoint = ModelEndpoint(
        id="local-router",
        endpoint="http://local:8000/v1",
        capabilities=[Capability.CODE_SIMPLE],
        cost=0,
        privacy=Privacy.LOCAL,
    )
    client = WorkerClient.from_endpoint(endpoint)
    client.execute(Task(goal="do it", capability_required=Capability.CODE_SIMPLE))

    assert fake.chat.completions.last_kwargs["model"] == "local-router"
