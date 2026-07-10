# AMD + Fireworks Deployment Notes

How TRIARC maps onto the hackathon's platforms. Two things earn judging points here:
using the **AMD platform** (GPU pod for Tier 1, AMD-hosted inference for Tiers 2–3) and
using **Gemma** for the Tier-2 coding model (qualifies for the Best AMD-Hosted Gemma
Project prize).

> Verify exact endpoint URLs, model identifiers, and prize terms against the official
> event resources before submitting — the names below are placeholders.

## Tier 1 — local model on the AMD GPU pod

- Runs a small model behind an **OpenAI-compatible** `/v1/chat/completions` endpoint on
  the AMD GPU pod (e.g. via a ROCm-compatible serving stack).
- Handles routing, classification, extraction, and simple edits — the bulk of steps —
  at **zero marginal cost**. This is the source of the cost win.
- Registered in `configs/models.yaml` as the `local-*` endpoints with `privacy: local`.
- `LOCAL_ENDPOINT`/`LOCAL_MODEL` are the only two knobs -- any OpenAI-compatible server
  works the same way the AMD pod does. **Ollama** (`http://localhost:11434/v1`) is a
  tested example for local dev: set `LOCAL_MODEL` to a model you've pulled
  (`ollama list`). It must support `response_format: json_schema` in strict mode, since
  the orchestrator never accepts free-text for routing decisions (architecture.md #4)
  -- confirmed working against `glm-4.7-flash` for both the single-task and full-plan
  schemas.

## Tiers 2–3 — Fireworks AI

- Both tiers are Fireworks-hosted OpenAI-compatible endpoints.
- **Tier 2 uses Gemma** for structured coding and test generation.
- **Tier 3 uses a larger Fireworks model** for deep reasoning, multi-file refactors, and
  subtle debugging — reached only via escalation.
- Both require `FIREWORKS_API_KEY` (env var only, never in config) and pass through the
  egress gatekeeper before any call.

## Containerization

The whole app ships as a container (an explicit submission requirement — not just the
code sandbox):

```
docker-compose.yml         # app service: build + port 8080 + workspace/configs mounts
docker/
└── Dockerfile              # the TRIARC app: orchestrator + management API
```

`docker compose up --build` brings up the management API on `:8080`; `.env` supplies
`FIREWORKS_API_KEY` and the Tier-1 endpoint URL. The code sandbox (docs/security.md)
runs each step's generated code in a plain `python:3.12-slim` container pulled at
runtime -- it doesn't need its own image, since it's just an execution target, not
app code.

## Config surface

```yaml
# configs/models.yaml
models:
  - id: local-router
    endpoint: ${LOCAL_ENDPOINT}          # AMD GPU pod, OpenAI-compatible
    capabilities: [route, extract, code_simple]
    cost: 0
    privacy: local
    tier: 1
  - id: gemma-coder
    endpoint: https://api.fireworks.ai/inference/v1
    model: ${FIREWORKS_GEMMA_MODEL}
    capabilities: [code_complex, tool_use]
    cost: 0.2
    privacy: cloud_ok
    tier: 2
  - id: frontier
    endpoint: https://api.fireworks.ai/inference/v1
    model: ${FIREWORKS_LARGE_MODEL}
    capabilities: [synthesis, debug, research]
    cost: 3.0
    privacy: cloud_ok
    tier: 3
```

## Judging alignment

- **Use of AMD platforms:** Tier 1 on the AMD GPU pod (free inference = the winning cost
  outcome); Tiers 2–3 via Fireworks on AMD hardware.
- **Gemma prize:** Tier 2 is Gemma, so a normal run exercises it on nearly every task.
- **Cost efficiency (Track 1 lineage):** the routing layer that keeps most steps on the
  free local tier is exactly the efficiency Track 1 measures — cite it as evidence the
  cost story is real.
