# Evolve — Architecture

## Product identity

**Evolve** is an independent AI Software Evolution Platform. It accepts any software project, builds a sourced cognitive map, proposes improvements with clear rationale, and executes only after human approval.

Projects are hard-isolated. Knowledge, workspaces, tasks, proposals, and evolution cycles never cross project boundaries.

## North-star quality bar

The destination is not a mediocre coding assistant. Evolve aims to operate at (and eventually beyond) the best contemporary AI engineering capability:

- **Polyglot mastery** — deep competence across mainstream and niche languages, frameworks, and ecosystems; language coverage expands continuously via Tree-sitter + language packs + coding models.
- **Proactive genius** — proposes high-leverage improvements with evidence, trade-offs, and blast-radius analysis — not cosmetic diffs.
- **Interactive builder** — users can issue direct requests; the system plans, implements, tests, and reports — still human-gated for merge/deploy.
- **Honesty under uncertainty** — never elevates guesses to facts; Independent Critic challenges weak plans.
- **Phased delivery** — we build this on the 12-phase roadmap. Genius-level coding arrives through Development Engine + multi-model gateway; we do not fake it before the foundations exist.

## Five layers

1. **Master Orchestrator** — goals, task routing, parallel specialist dispatch, rejection of unsupported results.
2. **Specialist departments** — understanding, engineering, design, product, development, security, quality, operations, documentation + Independent Critic.
3. **Knowledge & memory** — Project / Architecture / Decision / Execution memory with fact | inference | unverified provenance.
4. **Execution & tools** — Git branch apply (Phase 8), Docker sandbox plan, terminal, browser, DB, tests, CI/CD (never host execution of untrusted code by default; merge is human-gated).
5. **Control plane** — projects, proposals, approvals, roadmaps, reports, email notifications.

## Multi-model gateway

Agents bind to **roles** (`reasoning`, `coding`, `fast`, `multimodal`, `embedding`, `critic`), not hard-coded vendors. The Model Gateway resolves role → provider/model so models can be swapped without rewriting agents.

## Human-gated continuous evolution

```
periodic analysis (per project, isolated)
  → draft proposals with rationale / impact / risks
  → email owner (awaiting_approval)
  → human approve | reject | request revision
  → on approve: execute in sandbox + independent review
  → email completion report
  → human approve merge/deploy
  → update roadmap & knowledge
```

No autonomous coding or publishing without explicit human confirmation (unless a future scoped permission is granted).

## Phase 1 delivered foundation

- Project intake (Git / local path)
- Isolation namespaces + workspace roots
- Deterministic code scan
- LangGraph understanding pipeline
- Knowledge nodes with provenance
- Model Gateway
- FastAPI + Next.js admin shell (Arabic RTL neural dashboard)
- Proposal / decision / scorecard schemas (ready for later phases)
- Worker stub for evolution cron (disabled by default)

## Phase 2 Project Intelligence Engine

Four deterministic analyzers feed the knowledge map before any coding:

1. **Code Intelligence** — symbols, imports, API/page routes, entry flows
2. **Business Intelligence** — purpose from docs, actors, capabilities, contradictions
3. **Architecture Intelligence** — layers, coupling hotspots, change-impact anchors
4. **Visual Intelligence** — UI surface inventory + design-system signals

The orchestrator runs `run_project_intelligence` then `ProjectAnalyst` synthesis, always preserving fact / inference / unverified.

## Phase 3 Knowledge Graph

- Four memory layers: `project` · `architecture` · `decision` · `execution`
- Nodes always carry kind, confidence, source, evidence
- Edges link co-located knowledge, purpose→capabilities, layers→APIs, risks→layers, summary→facts
- Stale marking on refresh; query filters by layer/kind/category
- Polyglot language pack (`/system/languages`) expands continuously toward deep multi-language mastery

## Phase 4 Multi-Agent Orchestrator

Pipeline:

`intelligence → parallel specialists → ProjectAnalyst → IndependentCritic`

- **AgentRuntime** enforces permissions (no self-approve; code execution gated)
- Specialists run **in parallel** when independent: CodebaseExplorer, BusinessLogicAnalyst, SoftwareArchitect, SecurityAuditor, FeatureStrategist
- **IndependentCritic** challenges weak evidence and can set `needs_human`
- Every dispatch is recorded as an `AgentTask` under the project (`GET /api/projects/{id}/tasks`)
- Departments catalog: `GET /system/departments`

## Phase 5 Analysis Engine

After critique, the Analysis Engine scans intelligence for evidenced problems/opportunities across:

`quality · architecture · performance · security · ux · feature · integration · maintainability`

- Findings persist in `analysis_findings` (severity, confidence, evidence, recommendation)
- Also mirrored into knowledge nodes (`finding`, `analysis_summary`)
- API: `GET /api/projects/{id}/findings`

## Phase 6 Strategic Planning Engine

Findings → prioritized roadmap items (priority, complexity, impact, risks, acceptance criteria).

- Autonomously republished per project (`roadmaps` + `roadmap_items`)
- High-priority items marked `ready_for_proposal` (Phase 7)
- Project `settings.autonomy`: plan on, execute/merge/deploy off by default
- API: `GET /api/projects/{id}/roadmap`
- Worker may refresh plans when `EVOLUTION_CRON_ENABLED=true` (still never auto-executes)

## Phase 7 Proposals + Cursor-like chat

- Auto-draft `awaiting_approval` proposals from high-priority roadmap items
- Human actions: approve / reject / request revision (+ decision log)
- Interactive chat sessions with tools: list/read files, search knowledge, roadmap, draft proposal
- APIs:
  - `GET/POST .../proposals` (+ `/approve` `/reject` `/revise`)
  - `POST /api/projects/{id}/chat/sessions`
  - `POST /api/projects/{id}/chat/sessions/{sid}/messages`
