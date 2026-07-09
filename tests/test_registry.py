from pathlib import Path

import pytest

from orchestrator.registry import (
    ModelEndpoint,
    ModelRegistry,
    NoCapableEndpointError,
    escalate_capability,
)
from orchestrator.schema import Capability, Constraints, Privacy

CONFIG_PATH = Path(__file__).resolve().parent.parent / "configs" / "models.yaml"


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("LOCAL_ENDPOINT", "http://localhost:8000/v1")
    monkeypatch.setenv("FIREWORKS_GEMMA_MODEL", "accounts/fireworks/models/gemma-test")
    monkeypatch.setenv("FIREWORKS_LARGE_MODEL", "accounts/fireworks/models/large-test")


def test_loads_configs_models_yaml():
    registry = ModelRegistry.load(CONFIG_PATH)

    local = registry.get("local-router")
    assert local.endpoint == "http://localhost:8000/v1"
    assert local.privacy == Privacy.LOCAL
    assert Capability.ROUTE in local.capabilities


def test_missing_env_var_raises(monkeypatch):
    monkeypatch.delenv("LOCAL_ENDPOINT", raising=False)

    with pytest.raises(KeyError, match="LOCAL_ENDPOINT"):
        ModelRegistry.load(CONFIG_PATH)


def test_unknown_model_id_raises():
    registry = ModelRegistry.load(CONFIG_PATH)

    with pytest.raises(KeyError):
        registry.get("does-not-exist")


def test_resolve_picks_cheapest_direct_match():
    registry = ModelRegistry.load(CONFIG_PATH)

    endpoint = registry.resolve(Capability.CODE_COMPLEX, Constraints(privacy=Privacy.CLOUD_OK))

    assert endpoint.id == "gemma-coder"


def test_resolve_local_constraint_excludes_cloud_endpoints():
    registry = ModelRegistry.load(CONFIG_PATH)

    endpoint = registry.resolve(Capability.ROUTE, Constraints(privacy=Privacy.LOCAL))

    assert endpoint.id == "local-router"


def test_resolve_raises_when_local_constraint_has_no_capable_endpoint():
    registry = ModelRegistry.load(CONFIG_PATH)

    with pytest.raises(NoCapableEndpointError):
        registry.resolve(Capability.DEBUG, Constraints(privacy=Privacy.LOCAL))


def test_resolve_respects_max_cost():
    registry = ModelRegistry.load(CONFIG_PATH)

    with pytest.raises(NoCapableEndpointError):
        registry.resolve(
            Capability.DEBUG, Constraints(privacy=Privacy.CLOUD_OK, max_cost=1.0)
        )


def test_resolve_escalates_when_exact_capability_unavailable():
    registry = ModelRegistry(
        models=[
            ModelEndpoint(
                id="complex-only",
                endpoint="http://example.test",
                capabilities=[Capability.CODE_COMPLEX],
                cost=0.5,
                privacy=Privacy.CLOUD_OK,
            )
        ]
    )

    endpoint = registry.resolve(Capability.TOOL_USE, Constraints(privacy=Privacy.CLOUD_OK))

    assert endpoint.id == "complex-only"


def test_resolve_raises_when_no_endpoint_at_any_rung():
    registry = ModelRegistry(models=[])

    with pytest.raises(NoCapableEndpointError):
        registry.resolve(Capability.ROUTE, Constraints())


def test_escalate_capability_moves_up_one_rung():
    assert escalate_capability(Capability.CODE_SIMPLE) == Capability.TOOL_USE
    assert escalate_capability(Capability.DEBUG) == Capability.SYNTHESIS


def test_escalate_capability_raises_at_the_top_of_the_ladder():
    with pytest.raises(NoCapableEndpointError):
        escalate_capability(Capability.RESEARCH)
