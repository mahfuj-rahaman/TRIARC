# Roadmap — hackathon build phases

Rule: each phase ships something demoable. Build in dependency order; don't scaffold
later phases beyond stub interfaces.

## Phase 0 — Skeleton (½ day)
**Deliverable:** the container comes up and echoes a routed plan.
- [x] `orchestrator/schema.py` — the task schema (pydantic)
- [x] `orchestrator/registry.py` — model registry loading `configs/models.yaml`
- [x] Constrained-decoding client against Tier 1 (local endpoint)
- [ ] `docker compose up` brings up the app

## Phase 1 — Route + execute (core loop)  ⟵ THE PRODUCT
**Deliverable:** a real goal produces working code.
- [x] Router/planner loop: goal → plan → per-step capability emission
- [x] Registry resolution (Tier 1 → 2 → 3) with the routing algorithm
- [x] `orchestrator/servers/code_sandbox/` — containerized execution
- [x] `git` + `filesystem` MCP servers (workspace-scoped)
- [x] Test-run-read-fix loop

## Phase 2 — Escalation + gates
**Deliverable:** fail-upward works; irreversible actions are gated.
- [x] `confidence` + `escalation_reason` handling; reactive escalation ladder
- [x] Egress gatekeeper (secret/PII redaction before Tier 3)
- [x] Untrusted-ingress tagging for tool/web content
- [x] Confirmation-gate framework

## Phase 3 — Telemetry + cost demo  ⟵ THE MONEY-SHOT
**Deliverable:** the run summary that wins Track 3.
- [x] Per-step logging: tier, endpoint, tokens, cost, confidence, escalated
- [x] Run summary: actual vs all-frontier-baseline cost + savings
- [x] A simple visual (terminal table or small web view) for the demo video

## Phase 4 — Management UI (web + TUI)
**Deliverable:** a live dashboard over a running instance, in the browser and in the
terminal, over one shared API. Needs Phase 1–3 done first — nothing to display before
then.
- [ ] `orchestrator/api/` — FastAPI app: REST + WebSocket over run state, telemetry,
      model registry, and confirmation gates (see architecture.md §8)
- [ ] Run monitoring & control view — live goal/plan/per-step status, start/cancel a run
- [ ] Cost & routing telemetry view — per-step tier/endpoint/tokens/cost, escalation
      history, actual-vs-baseline savings
- [ ] Model registry editor — view/edit `configs/models.yaml` entries
- [ ] Confirmation gate inbox — approve/deny pending gates, view egress redaction log
- [ ] `ui/web/` — React + TypeScript client
- [ ] `ui/tui/` — Python Textual client
- [ ] Both clients hit only the management API — no direct filesystem/log reads

## Phase 5 — Packaging & submission
- [ ] Whole-app container verified runnable from README instructions
- [ ] `web` MCP server for lookups (optional but nice)
- [ ] README + docs finalized; MIT LICENSE added
- [ ] Cover image (routing diagram), demo video, slides
- [ ] Gemma confirmed as the Tier-2 model (Gemma prize)

## Cut lines (if time runs short)
Drop in this order: the full Management UI (Phase 4 — Phase 3 already ships a minimal
terminal table / small web view, which covers the demo) → `web` server → visual polish
on the cost view → predictive escalation (keep reactive). **Never cut:** the core loop,
the security gates, and the cost telemetry — those are the three things the submission
is judged on.
