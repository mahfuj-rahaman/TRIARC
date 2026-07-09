import json

import pytest

from orchestrator.registry import ModelEndpoint
from orchestrator.schema import Capability, Constraints, Privacy, Task
from orchestrator.security.egress import EgressGatekeeper, PrivacyConsentError
from orchestrator.worker_client import WorkerClient
from tests._openai_fakes import install_fake_openai


def _cloud_client() -> WorkerClient:
    return WorkerClient(
        endpoint="https://fireworks.test/v1",
        model="gemma",
        gatekeeper=EgressGatekeeper(log_path=None),
    )


def test_execute_returns_task_with_worker_result(monkeypatch):
    content = json.dumps({"result": "print('hello')", "confidence": 0.9})
    fake = install_fake_openai(monkeypatch, "orchestrator.worker_client", content)

    client = _cloud_client()
    task = Task(
        goal="write hello world script",
        capability_required=Capability.CODE_SIMPLE,
        context_refs=["hello.py"],
        constraints=Constraints(privacy=Privacy.CLOUD_OK),
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

    client = _cloud_client()
    task = Task(
        goal="fix the bug",
        capability_required=Capability.DEBUG,
        constraints=Constraints(privacy=Privacy.CLOUD_OK),
    )

    client.execute(task, feedback="AssertionError: expected 2 got 1")

    messages = fake.chat.completions.last_kwargs["messages"]
    assert "AssertionError" in messages[-1]["content"]


def test_execute_redacts_secrets_before_sending(monkeypatch):
    content = json.dumps({"result": "ok", "confidence": 0.9})
    fake = install_fake_openai(monkeypatch, "orchestrator.worker_client", content)

    client = _cloud_client()
    task = Task(
        goal="use key sk-abcdEFGH12345678zzz to call the api",
        capability_required=Capability.CODE_SIMPLE,
        constraints=Constraints(privacy=Privacy.CLOUD_OK),
    )

    client.execute(task)

    messages = fake.chat.completions.last_kwargs["messages"]
    assert "sk-abcdEFGH12345678zzz" not in messages[-1]["content"]
    assert "[REDACTED:api_key]" in messages[-1]["content"]


def test_execute_rejects_cloud_call_without_task_consent(monkeypatch):
    install_fake_openai(monkeypatch, "orchestrator.worker_client", json.dumps({"result": "ok", "confidence": 0.9}))

    client = _cloud_client()
    task = Task(goal="do it", capability_required=Capability.CODE_SIMPLE)  # defaults to privacy: local

    with pytest.raises(PrivacyConsentError):
        client.execute(task)


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
