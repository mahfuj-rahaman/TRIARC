# TRIARC — The Autonomous AI Developer That Routes Before It Reasons

![TRIARC routing diagram](docs/assets/routing-diagram.svg)

**AMD Developer Hackathon: ACT II — Track 1 (Hybrid Token-Efficient Routing Agent)**

TRIARC is an autonomous AI developer that plans, writes, runs, and debugs code by
routing every step to the *cheapest capable model* — the lowest-cost Fireworks-hosted
model first, escalating to larger Fireworks models only when the task actually demands
it. A small orchestrator decides **who** does the work; large models are called on
demand, never by default.

The name comes from the **tri-agent architecture** at its core: one orchestrator that
routes, plus the reasoning tiers it escalates to — three roles, one arc from plan to
shipped code.

> **Lineage.** TRIARC is the hackathon incarnation of a from-scratch, local-first
> personal AI system built on three LoRA-specialized roles (Orchestrator, Agent,
> Researcher). The fundamentals are identical — capability-based routing, an escalation
> ladder, schema-enforced inter-agent messages, MCP tools, a three-faced security plane.
> For the hackathon, all three tiers run against **Fireworks AI-hosted models** — the
> original design targeted a local model on AMD GPU hardware for Tier 1, but the AMD
> GPU credits we were expecting didn't come through in time, so Tier 1 also routes to a
> low-cost Fireworks endpoint instead. The routing/escalation logic is identical either
> way; only the Tier 1 endpoint differs from the original plan.
>
> **Development tooling disclosure.** TRIARC was built with the help of Claude
> (Anthropic) as a coding/debugging assistant during development. Claude is not part of
> TRIARC's runtime — at inference time, TRIARC only calls Fireworks AI-hosted models.

---

## The problem

Autonomous coding agents are expensive and brittle. Most push every step — trivial file
edits, boilerplate, simple lookups — through a large frontier model, burning tokens on
work a tiny model could do, and they bluff confidently when a task exceeds their reach
instead of escalating. **Cost scales with ambition, and reliability doesn't.**

TRIARC's answer is to separate *orchestration* from *reasoning*:

- A small, fast **orchestrator** does only classification, decomposition, and routing.
  It never attempts open-ended synthesis.
- For each sub-task it emits a required **capability** (never a model name).
- A **registry** resolves that capability to the cheapest endpoint that satisfies it.
- Every result carries a `confidence` score and an `escalation_reason` — the system
  **fails upward instead of bluffing**, retrying on a stronger endpoint rather than
  defaulting every task to the most expensive tier out of caution.

---

## The three tiers (routing contract)

The orchestrator emits `capability_required`; the registry resolves it to an endpoint.
No component ever hardcodes a model name — swapping a model is a one-line config change.

All three tiers are Fireworks AI-hosted models — Tier 1 was originally scoped for a
local model on AMD GPU hardware, but ran on Fireworks instead due to AMD GPU credit
availability during the event. See the lineage note above.

| Tier | Endpoint | Handles | Cost |
|---|---|---|---|
| **Tier 1** | Fireworks-hosted low-cost model (e.g. GLM-5.2) | classification, extraction, simple edits, routing | free / lowest |
| **Tier 2** | Fireworks mid (**Gemma**) | structured coding, test generation | low |
| **Tier 3** | Fireworks large (frontier) | deep reasoning, multi-file refactors, subtle debugging | high |

See [docs/architecture.md](docs/architecture.md) for the full design and
[docs/routing.md](docs/routing.md) for the routing/escalation mechanics.

---

## System at a glance

```
Goal in  ──▶  Orchestrator (small model, constrained JSON decode)
                 │  classify → decompose → emit capability_required per step
                 ▼
             Model Registry ── resolves capability → cheapest capable endpoint
                 │   Tier 1: Fireworks low-cost     classify, extract, simple edits
                 │   Tier 2: Fireworks mid (Gemma)  structured coding, tests
                 │   Tier 3: Fireworks large        deep reasoning, refactor, hard debug
                 ▼
             Tool layer (MCP) ── code-sandbox · git · filesystem · web
                 │   every external result tagged UNTRUSTED
                 ▼
             Execute → run tests → read failures → loop / escalate
                 │   each result carries {confidence, escalation_reason}
                 ▼
             Security plane on every hop:
               egress redaction · untrusted-ingress tagging · confirmation gates
```

---

## Evaluation / batch mode (this is what the grading harness runs)

The published image runs headless, one-shot: it reads a batch of tasks, routes and
executes each one through the registry above, and writes results — no server, no
manual interaction.

```bash
docker pull ghcr.io/hoodk123/triarc:latest

docker run --rm \
  -v "$(pwd)/input:/input:ro" \
  -v "$(pwd)/output:/output" \
  -e FIREWORKS_API_KEY=<your-key> \
  -e FIREWORKS_GEMMA_MODEL=<model-id> \
  -e FIREWORKS_LARGE_MODEL=<model-id> \
  -e LOCAL_ENDPOINT=<tier-1 endpoint> \
  -e LOCAL_MODEL=<tier-1 model-id> \
  ghcr.io/hoodk123/triarc:latest
```

`input/tasks.json` is a JSON array of `{"task_id": "...", "goal": "..."}` objects.
The container writes `output/results.json` — one `{task_id, goal, result, confidence}`
entry per task — and exits with code `0`. This is the `triarc run-task` command
(`orchestrator/cli.py`), invoked automatically by the image's default `CMD`.

Build it yourself instead of pulling:

```bash
git clone https://github.com/<you>/triarc.git && cd triarc
cp .env.example .env            # add FIREWORKS_API_KEY and Tier 1 endpoint
docker compose up --build --remove-orphans
```

---

## Interactive / development mode

For iterating on a real coding task with the full plan → execute → test → fix loop
(sandboxed `pytest` runs, retries, escalation), use the CLI directly against a live
workspace — this path expects an actual codebase mounted in and a test suite to run,
so it's a development tool, not what the grading harness exercises:

```bash
uv run triarc run "add JWT auth to this Flask app and write tests" --execute
```

### Management UI (optional, local only)

A separate `serve` mode exposes a management API for two thin dashboard clients — run
monitoring, cost & routing telemetry, the model registry editor, and the
confirmation-gate inbox. Neither the API nor the UI is used by automated evaluation.

```bash
uv run triarc serve --host 127.0.0.1 --port 8080

# web dashboard
cd ui/web && npm install && npm run dev       # http://localhost:5173

# terminal dashboard
uv pip install -e ".[tui]"
uv run python -m ui.tui.app                    # from repo root
```

---

## Repository layout

```
triarc/
├── README.md                  # this file
├── LICENSE                    # MIT
├── docs/
│   ├── architecture.md        # system design (source of truth)
│   ├── routing.md             # routing + escalation mechanics
│   ├── features.md            # feature catalogue (what TRIARC does)
│   ├── security.md            # three-faced security plane
│   ├── amd-fireworks.md       # AMD + Fireworks deployment notes
│   └── roadmap.md             # build phases in dependency order
├── orchestrator/              # registry, router loop, task schema, develop loop
│   ├── security/                # egress gatekeeper, ingress tagging, confirmation gates
│   ├── servers/                # first-party MCP servers (code-sandbox, git, filesystem, web)
│   └── api/                    # management API: REST + polling WebSocket (architecture.md §8)
├── ui/
│   ├── web/                    # React + TypeScript management dashboard
│   └── tui/                    # Python Textual management dashboard
├── configs/                   # model registry, MCP servers, policies (YAML)
├── input/                     # tasks.json for batch/evaluation runs
├── output/                    # results.json written by batch runs
├── workspace/                  # the sandboxed project directory a run operates on
├── tests/                      # pytest suite for orchestrator/, orchestrator/api/, ui/tui/
└── docker/                    # container definitions
```

---

## Design principles (do not violate)

1. **Small model routes; big models reason.** The orchestrator classifies, decomposes,
   and picks the cheapest capable endpoint. It never does open-ended synthesis.
2. **Everything pluggable through two standards.** Models are OpenAI-compatible
   endpoints in a capability registry; tools are MCP servers. Adding or upgrading a
   model is a config change, zero code change.
3. **Structured output is enforced, not hoped for.** All routing and tool decisions use
   schema-constrained decoding. Model wobble must not break the pipeline.
4. **Fail upward, never bluff.** Every task result carries `confidence` and an
   `escalation_reason`.
5. **Security is three-faced.** Egress (redact secrets before any cloud call), ingress
   (all external content tagged untrusted), and confirmation gates on every irreversible
   action — for every actor, every time.

---

## Why it's a startup, not a demo

Every commercial coding-agent user has the same two complaints: *it costs too much* and
*it does dumb things confidently.* TRIARC's routing layer is a direct, measurable answer
to the first; its confidence-gated escalation is a direct answer to the second. The
routing intelligence is the moat, wrapped into a real autonomous-developer product.

---

## License

MIT. See [LICENSE](LICENSE).