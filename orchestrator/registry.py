"""Model registry: single source of model access (architecture.md #3).

Loads configs/models.yaml. No other component may know a model URL or name.
Capability -> endpoint resolution (the routing algorithm) is Phase 1; this module
only loads and looks up entries by id.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import yaml
from pydantic import BaseModel

from orchestrator.schema import Capability, Constraints, Privacy

_ENV_VAR = re.compile(r"\$\{([A-Z0-9_]+)(?::-(.*?))?\}")

# Escalation ladder (docs/routing.md "Capabilities" table, ascending tier). Resolution
# starts at the requested capability and, if no endpoint satisfies it, retries at each
# rung above -- the same "escalate one level" step the resolution algorithm specifies.
_ESCALATION_LADDER: list[Capability] = [
    Capability.ROUTE,
    Capability.EXTRACT,
    Capability.CODE_SIMPLE,
    Capability.TOOL_USE,
    Capability.CODE_COMPLEX,
    Capability.DEBUG,
    Capability.SYNTHESIS,
    Capability.RESEARCH,
]


class NoCapableEndpointError(RuntimeError):
    """No registered endpoint satisfies a capability requirement (or any escalation)."""


class ModelEndpoint(BaseModel):
    id: str
    endpoint: str
    model: str | None = None
    capabilities: list[Capability]
    cost: float
    privacy: Privacy
    tier: int | None = None


class ModelRegistry(BaseModel):
    models: list[ModelEndpoint]

    @classmethod
    def load(cls, path: str | Path) -> "ModelRegistry":
        raw = Path(path).read_text()
        resolved = _ENV_VAR.sub(_lookup_env, raw)
        data = yaml.safe_load(resolved)
        return cls.model_validate(data)

    def get(self, model_id: str) -> ModelEndpoint:
        for endpoint in self.models:
            if endpoint.id == model_id:
                return endpoint
        raise KeyError(f"no model registered with id {model_id!r}")

    def resolve(self, capability: Capability, constraints: Constraints) -> ModelEndpoint:
        """Resolve a capability requirement to the cheapest satisfying endpoint.

        Implements the resolution algorithm in docs/routing.md: filter to endpoints
        whose capabilities satisfy the requirement, drop those violating privacy or
        max_cost, and pick the cheapest survivor. If none survive, escalate the
        capability requirement one rung up the ladder and retry.
        """
        rung = _ESCALATION_LADDER.index(capability)
        for candidate in _ESCALATION_LADDER[rung:]:
            survivors = [
                endpoint
                for endpoint in self.models
                if candidate in endpoint.capabilities
                and _privacy_satisfied(endpoint.privacy, constraints.privacy)
                and (constraints.max_cost is None or endpoint.cost <= constraints.max_cost)
            ]
            if survivors:
                return min(survivors, key=lambda endpoint: endpoint.cost)
        raise NoCapableEndpointError(
            f"no endpoint satisfies capability_required={capability.value!r} "
            f"(or any escalation) under constraints={constraints!r}"
        )


def escalate_capability(capability: Capability) -> Capability:
    """Move CAPABILITY one rung up the escalation ladder (docs/routing.md).

    Used for reactive (fail-upward) escalation: a step whose result carries low
    confidence or an escalation_reason re-resolves at the next rung, even though the
    current endpoint already satisfied the original capability.
    """
    rung = _ESCALATION_LADDER.index(capability)
    if rung + 1 >= len(_ESCALATION_LADDER):
        raise NoCapableEndpointError(
            f"capability_required={capability.value!r} is already at the top of the "
            "escalation ladder"
        )
    return _ESCALATION_LADDER[rung + 1]


def _privacy_satisfied(endpoint_privacy: Privacy, task_privacy: Privacy) -> bool:
    if task_privacy == Privacy.LOCAL:
        return endpoint_privacy == Privacy.LOCAL
    return True


def _lookup_env(match: re.Match[str]) -> str:
    name, default = match.group(1), match.group(2)
    try:
        return os.environ[name]
    except KeyError as exc:
        if default is not None:
            return default
        raise KeyError(
            f"configs/models.yaml references ${{{name}}}, "
            "but it is not set in the environment"
        ) from exc
