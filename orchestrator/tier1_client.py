"""Constrained-decoding client against Tier 1 (architecture.md #2, #4).

Sends a goal to the local Tier-1 endpoint and gets back a schema-validated Task
via JSON-schema-constrained decoding, never free text. Decomposing a goal into a
multi-step plan is the Phase 1 router/planner loop; this client performs the
single classification call that loop will build on.
"""

from __future__ import annotations

import json

from openai import OpenAI

from orchestrator.schema import Plan, Task

_SYSTEM_PROMPT = (
    "You are the TRIARC orchestrator's routing step. You do not solve the user's "
    "goal. Classify it: choose the single capability_required it needs (route, "
    "extract, code_simple, code_complex, tool_use, research, synthesis, or debug), "
    "set constraints.privacy to 'local' unless the goal clearly requires external "
    "or cloud knowledge, and set confidence to your own 0-1 confidence in that "
    "classification. Leave result and escalation_reason null -- routing does not "
    "execute the task."
)

_PLAN_SYSTEM_PROMPT = (
    "You are the TRIARC orchestrator's planning step. Decompose the user's goal into "
    "an ordered list of sub-tasks needed to accomplish it -- do not solve any of them "
    "yourself. For each step, write a concise sub-goal describing exactly one unit of "
    "work, choose the single capability_required it needs (route, extract, "
    "code_simple, code_complex, tool_use, research, synthesis, or debug), set "
    "constraints.privacy to 'local' unless the step clearly requires external or "
    "cloud knowledge, and set confidence to your own 0-1 confidence in that step's "
    "classification. Leave result and escalation_reason null on every step -- "
    "planning does not execute tasks. Order steps so each one only depends on steps "
    "before it."
)


class Tier1Client:
    """Talks to the Tier-1 local endpoint using JSON-schema-constrained decoding."""

    def __init__(self, endpoint: str, model: str = "tier1-router") -> None:
        self._client = OpenAI(base_url=endpoint, api_key="not-needed")
        self._model = model

    def route(self, goal: str) -> Task:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": goal},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "task",
                    "schema": Task.model_json_schema(),
                    "strict": True,
                },
            },
        )
        content = response.choices[0].message.content
        data = json.loads(content)
        data["goal"] = goal
        return Task.model_validate(data)

    def plan(self, goal: str) -> Plan:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": _PLAN_SYSTEM_PROMPT},
                {"role": "user", "content": goal},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "plan",
                    "schema": Plan.model_json_schema(),
                    "strict": True,
                },
            },
        )
        content = response.choices[0].message.content
        data = json.loads(content)
        data["goal"] = goal
        return Plan.model_validate(data)
