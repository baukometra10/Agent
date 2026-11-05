# Build phases

| Phase | Deliverable |
|------|-------------|
| 1 | Core Engine, project intake, isolation, Model Gateway, initial understanding, admin shell |
| 2 | Project Intelligence (code / business / architecture / visual) — **foundation landed** |
| 3 | Knowledge Graph + four memory layers + freshness — **foundation landed** |
| 4 | Multi-Agent Orchestrator across departments + Critic — **foundation landed** |
| 5 | Analysis Engine — **foundation landed** |
| 6 | Strategic Planning Engine — **foundation landed** |
| 7 | Proposal & Approval System + Cursor-like chat — **foundation landed** |
| 8 | Software Development Engine (sandboxed Git branches) — **foundation landed** |
| 9 | Design & UI Engineering Engine — **foundation landed** (tokens/wireframe + proposals) |
| 10 | Testing, Security & Quality Engine — **foundation landed** (heuristic review pack) |
| 11 | Deployment & Continuous Evolution — **foundation landed** (plan/confirm simulate + evolve cycle) |
| 12 | Multi-project control plane at scale — **foundation landed** |
| 13 | Live model providers (OpenAI + Anthropic) — **foundation landed** |
| 14 | Ownership doctrine: Intelligent Router + Distillation scaffold — **foundation landed** |
| 15 | Eval harness + host probe + PI LoRA job pipeline — **foundation landed** |
| 16 | Ollama host wire + coding specialty + continual learning cycle — **foundation landed** |
| 17 | Reasoning + Critic specialties + dataset grow + promote path — **foundation landed** |
| 18 | ChiefAgent + dynamic worker pool (spawn/train when busy) — **foundation landed** |
| 19 | Fast eval model + Vision specialty + Chief→distill feedback — **foundation landed** |
| 20 | Promote-all specialties + cloud deploy adapters — **foundation landed** |
| 21 | Project long-term memory + prefer promoted internals — **foundation landed** |
| 22 | Fast ownership handoff (learn → retire teachers) — **foundation landed** |
| 23 | Learn-from-everything + intake advisory + مساعد الطيار (sandbox) — **foundation landed** |
| 24 | Autopilot background loop + pause on manual chat + visible toggle — **foundation landed** |
| 25 | مساعد الطيار reports in notifications + sandbox security/quality review — **foundation landed** |
| 26 | Sandbox experimental patches + diffs + `/copilot` page — **foundation landed** |
| 27 | Promote approved sandbox → project + handoff_ready no-escalate — **foundation landed** |
| 28 | Coverage meter to 85% + urgent security reports — **foundation landed** |
| 29 | Retire teachers for handoff_ready specialties — **foundation landed** |
| 30 | Measured owned coverage climb (persist metrics + `/coverage/climb`) — **foundation landed** |
| 31 | Real LoRA train hook (peft/transformers + tiny fallback) — **foundation landed** |
| 32 | Webhook/Slack alerts for مساعد الطيار reports — **foundation landed** |
| 33 | Promote sandbox→project E2E smoke — **foundation landed** |
| 34 | Owned embeddings specialty + cost/task metrics — **foundation landed** |
| 35 | Copilot one-click approve+execute (isolated branch) — **foundation landed** |
| 36 | Project-isolated embeddings store + search API — **foundation landed** |
| 37 | Polyglot language-pack expansion (Zig/Solidity/GraphQL/…) — **foundation landed** |
| 38 | Unified workspace UI + Cursor-like Command Dock — **foundation landed** |
| 39 | Self-maintenance engine (`/maintain` + background heal) — **foundation landed** |
| 40 | Fixed sidebar + user/admin split + email login + tokens/entitlements — **foundation landed** |
| 41 | Spixa by Suppix AI + web console (usage/billing) + payment unlock — **foundation landed** |
| 42 | Plan gates in nav + token chip + usage charts + chat spend — **foundation landed** |
| 43 | Web IDE (open/edit files) + desktop download from website — **foundation landed** |
| 44 | IDE agent panel + open folder + Ctrl+P + desktop folder dialog — **foundation landed** |
| 45 | Close gaps: Monaco + Stripe checkout + agent apply + desktop builders + Spixa rename — **foundation landed** |
| 46 | Dual verify (email+SMS) + admin users/abuse live alerts — **foundation landed** |
| 47 | Internal Intelligence First + AI Cost Efficiency meter — **foundation landed** |
| 48 | Rapid Learning 7-layer system + Multi-Agent / execution labs — **foundation landed** |
| 49 | Model Development Factory (5 engines + human-gated releases) — **foundation landed** |
| 50 | Factory gates everywhere + regression vs approved + ownership factory meter — **foundation landed** |
| 51 | Practical proof track: real LoRA JSONL fix + coding proof API + successive gains — **foundation landed** |
| — | Real LoRA/GPU + Coding prod proof — **deferred** until private staging deploy, then public |
| **I1–I6** | Spixa Intelligence Roadmap (see `docs/SPIXA_INTELLIGENCE.md`) — **adopted**, builds on 1–51 |
| 52 | Maturity gates + Ownership Registry + Independence probe + Evolution dashboard — **foundation landed** |

Do not advance a phase until the previous phase’s quality gates pass.

## Ownership track (Teacher → Student → Self-Owned)

See `docs/MODEL_OWNERSHIP.md`. Runtime milestones:

| Step | Work | Status |
|------|------|--------|
| 1 | Gateway manages teachers + internal family | landed |
| 2 | Host base internal model (OpenAI-compatible URL) | probe API + `scripts/check-internal-host.ps1` |
| 3 | Eval / compare harness (held-out, promote gates) | landed |
| 4 | Distillation pipeline (verify → JSONL) | landed |
| 5 | Project-Intelligence specialty seed + LoRA job | foundation landed |
| 6 | Coding specialty seed + LoRA + eval suite | foundation landed |
| 7 | Reasoning specialty seed + eval | foundation landed |
| 8 | Critic specialty seed + eval | foundation landed |
| 9 | Vision specialty seed + eval + Chief worker | foundation landed |
| 10 | Continual learning cycle + grow-all + fast eval model | foundation landed |
| 11–12 | Reduce external share toward 80–90% successful tasks | climbing via `/coverage/climb` + retired teachers |
| 13 | Per-project LTM (every word, hard isolation) | foundation landed |
| 14 | Fast handoff: chat/LTM → student fuel + readiness map | foundation landed |

### Phase 21 notes

- `ProjectLongTermMemory` — transcript.jsonl under each workspace + conversation knowledge layer
- Chat + MasterConductor + Chief workers bind to workspace/namespace and recall standing instructions
- `GET/POST /api/projects/{id}/memory` (+ `/remember`, `/layers`)
- Router: `PREFER_PROMOTED_INTERNAL` / `PROMOTED_NO_ESCALATE` keep owned specialists off teachers when ready

### Phase 22 notes

- `OwnershipHandoff` — specialty readiness (promoted + enough examples) + rapid distill
- Every successful chat turn fuels students when `FAST_HANDOFF_ENABLED=true`
- `GET /system/ownership/handoff` · `POST /system/ownership/handoff/distill-project`
- Settings UI: جاهزية النقل + تقطير سريع من ذاكرة المشروع

### Phase 23 notes

- `ExperienceJournal` — learn from success **and** failure/error/rejection (`LEARN_FROM_EVERYTHING`)
- `IntakeAdvisor` — after understanding: engineering brief + improvements/risks → gated proposals
- **مساعد الطيار / Autopilot** — clones to `data/autopilot/runs/*` only; never writes originals; email/queue report
- APIs: `GET/POST /system/autopilot` (+ `/enable` `/disable` `/run`); Control Plane UI controls
- Doctrine: genius agent = absorb every outcome; unattended mode proposes, human approves

### Phase 24 notes

- Background `autopilot` loop starts with API lifespan; cycles every `AUTOPILOT_INTERVAL_SECONDS` while enabled
- Manual chat → `pause_for_manual` (toggle shows معلّق); `/system/autopilot/resume` or re-enable clears pause
- Topbar toggle always visible: يدوي / آلي / معلّق

### Phase 25 notes

- Official Arabic name: **مساعد الطيار** (was misread as التيار — one letter)
- `GET /system/autopilot/reports` (+ `/latest`); NotificationsMenu shows report cards
- Sandbox review adds security/quality/risk heuristics without touching originals

### Phase 26 notes

- `apply_experimental_patches` writes only under marked `.evolve-sandbox` clones (SUGGESTIONS.md, .gitignore harden, smoke test, experiment.diff)
- Opens one human-gated `copilot_sandbox` proposal with diff preview in evidence
- Dedicated UI: `/copilot` — toggle, run now, latest diff, report history

### Phase 27 notes

- `promote_sandbox_experiment` copies allowlisted sandbox files into project `repo/` after approve+execute
- `DevelopmentEngine` short-circuits `origin=copilot_sandbox` to promote path (merge still human-gated)
- Router: `handoff_ready` specialties refuse teacher escalate when `prefer_promoted`

### Phase 28 notes

- `GET /system/ownership/coverage` — meter toward 85% (router coverage + specialty readiness blend)
- مساعد الطيار reports mark `urgent` on security hits; email subject `[مساعد الطيار · عاجل]`
- Promote success recorded in ExperienceJournal; `/copilot` shows coverage KPIs

### Phase 29 notes

- Persist retired specialties in `data/learning/handoff/retired_teachers.json`
- `AUTO_RETIRE_READY_TEACHERS` auto-retires when handoff_ready; router refuses teacher escalate
- APIs: `GET/POST /system/ownership/retire` · `POST /system/ownership/restore`
- Settings UI: إيقاف معلّمي التخصصات الجاهزة / استعادة معلّم

### Phase 30–33 notes

- Router metrics persist under `data/learning/ownership/router_metrics.json`
- `POST /system/ownership/coverage/climb` drives owned completions; UI: رفع التغطية الداخلية
- `LORA_REAL_TRAIN_ENABLED` → `app/training/real_lora.py` (tiny-gpt2 fallback when base missing)
- `NOTIFICATION_WEBHOOK_URL` Slack/JSON webhook on reports (`URGENT_ONLY` optional)
- Promote E2E: `tests/test_promote_e2e.py`

### Phase 34–35 notes

- Embeddings curriculum + eval suite; `POST /system/ownership/seed/embeddings`; grow/promote include embeddings
- Router tracks `estimated_cost_usd` + `cost_per_successful_task_usd` (shown on `/copilot` + settings)
- `/copilot`: موافقة وتنفيذ (فرع معزول) → approve then execute; merge stays human-gated

### Phase 36–37 notes

- `{workspace}/memory/embeddings/index.jsonl` — owned local hash vectors; hard project isolation
- APIs: `GET/POST /api/projects/{id}/memory/embeddings` · `POST .../embeddings/search`
- Language packs: Zig, Nim, Solidity, GraphQL, Prisma, F#, OCaml, … (`GET /system/languages`)

### Phase 38–39 notes

- Unified workspace chrome (`PageHeader`) on all pages except home dashboard + fleet control-plane
- Command Dock: floating «أمر» / `Ctrl+J` → project chat (Cursor-like manual orders)
- Self-maintenance: `GET/POST /system/maintain` · UI `/maintain` · auto every 3rd autopilot tick

### Phase 15–16 APIs

- `GET /system/ownership` — dashboard (host, adapters, latest eval)
- `GET /system/ownership/host` — internal host readiness
- `POST /system/ownership/eval?specialty=project_intelligence|coding`
- `POST /system/ownership/seed/project-intelligence` + `/all`
- `POST /system/ownership/seed/coding` — curated curriculum + repo snippets
- `POST /system/ownership/train/lora` — prepare adapter + eval gates
- `POST /system/ownership/learning/cycle` — seed → train → held-out eval
- Scripts: `bootstrap-internal-host.ps1`, `check-internal-host.ps1`

## Phase 12 notes

- `GET /api/control-plane/fleet` — per-project cards (isolation, approvals, findings, last evolve)
- `POST /api/control-plane/evolve-all` — sequential isolated evolution (never parallel across projects)
- `POST /api/projects/blank` — UI intake for empty scaffolded workspaces
- UI: `/control-plane` fleet board + `/projects` create form

## Phase 13 notes

- Model Gateway live adapters: OpenAI chat/embeddings + Anthropic messages (httpx)
- Offline simulate when keys missing; `MODEL_GATEWAY_FORCE_SIMULATE` for tests
- `GET /system/models` provider readiness (no secrets); `POST /system/models/probe`
- Settings UI shows provider status + probe button
