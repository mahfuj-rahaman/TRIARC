"""Generic worker client for Tier 2/3 endpoints (architecture.md #2, #4).

Unlike Tier1Client (routing-only, local Tier 1), this executes a task against any
OpenAI-compatible endpoint -- Fireworks-hosted Gemma or the frontier model. Schema-
constrained decoding keeps the result machine-readable (the task schema) instead of
free text; `result` carries the produced file content for code-writing capabilities.
`context_refs[0]`, if present, is the file this task's result should be written to --
the develop loop (orchestrator/develop_loop.py) is what actually writes it.
"""

from __future__ import annotations

import json
import os

from openai import OpenAI

from orchestrator.registry import ModelEndpoint
from orchestrator.schema import Task

_SYSTEM_PROMPT = (
    "You are a TRIARC worker executing exactly one sub-task of a larger plan. Produce "
    "the file content described by the goal and write it to `result` verbatim -- no "
    "commentary, no markdown fences. `context_refs[0]`, if present, is the file you "
    "are writing. Set `confidence` to your own 0-1 confidence that the result is "
    "correct; if you cannot complete the goal, set a low confidence and explain why in "
    "`escalation_reason`."
)


class WorkerClient:
    """Talks to a Tier 2/3 endpoint to execute a single task."""

    def __init__(self, endpoint: str, model: str) -> None:
        self._client = OpenAI(
            base_url=endpoint, api_key=os.environ.get("FIREWORKS_API_KEY", "not-needed")
        )
        self._model = model

    @classmethod
    def from_endpoint(cls, endpoint: ModelEndpoint) -> "WorkerClient":
        return cls(endpoint=endpoint.endpoint, model=endpoint.model or endpoint.id)

    def execute(self, task: Task, feedback: str | None = None) -> Task:
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": task.goal},
        ]
        if feedback:
            messages.append(
                {
                    "role": "user",
                    "content": f"The previous attempt failed with this output:\n{feedback}\nFix it.",
                }
            )

        response = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
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
        data["task_id"] = task.task_id
        data["goal"] = task.goal
        data["capability_required"] = task.capability_required.value
        data["context_refs"] = task.context_refs
        return Task.model_validate(data)
