"""The task schema — single source of truth (features.md #4)."""

from __future__ import annotations

import uuid
from enum import Enum

from pydantic import BaseModel, Field


class Capability(str, Enum):
    ROUTE = "route"
    EXTRACT = "extract"
    CODE_SIMPLE = "code_simple"
    CODE_COMPLEX = "code_complex"
    TOOL_USE = "tool_use"
    RESEARCH = "research"
    SYNTHESIS = "synthesis"
    DEBUG = "debug"


class Privacy(str, Enum):
    LOCAL = "local"
    CLOUD_OK = "cloud_ok"


class Constraints(BaseModel):
    privacy: Privacy = Privacy.LOCAL
    max_cost: float | None = None


class Task(BaseModel):
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    goal: str
    capability_required: Capability
    context_refs: list[str] = Field(default_factory=list)
    constraints: Constraints = Field(default_factory=Constraints)
    result: str | None = None
    confidence: float = 0.0
    escalation_reason: str | None = None


class Plan(BaseModel):
    """An ordered decomposition of a goal into sub-tasks (architecture.md #4)."""

    goal: str
    steps: list[Task] = Field(default_factory=list)
