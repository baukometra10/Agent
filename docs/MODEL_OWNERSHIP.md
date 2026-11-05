# Internal Intelligence First

**Doctrine:** الذكاء الداخلي أولًا — الخارجي عند الضرورة فقط.

**Adopted product strategy:** [SPIXA_INTELLIGENCE.md](./SPIXA_INTELLIGENCE.md) — Spixa Proprietary Intelligence Ecosystem (six specialties + Orchestrator; adapters-first ownership).

Use external intelligence to *birth* internal intelligence — never to remain forever dependent on it. Every task is fuel for owned models; every successful distill reduces future external spend. **Never trade intelligence for cheapness** — escalate when quality gates fail.

**AI Cost Efficiency** tracks: internal task ratio, external cost, internal run cost, training cost, result quality, and cost per successful task (`GET /system/ownership/cost-efficiency`).

**Distillation Engine** is a core pillar from day one — not a future add-on.

**Model Development Factory** (`docs/MODEL_FACTORY.md`) binds five engines — Learning, Distillation, Synthetic Data, Evaluation Lab, Self-Improvement — under **human-gated** production releases. Eval pass creates a proposal; only explicit approve ships adapters to the router.

Operational goal (not a calendar promise): **80–90% of successful tasks** served by owned models after maturity. Measure successful tasks, not raw request counts. External models escalate only when tools/tests/quality gates demand it.

```
External Teacher Models → Internal Student Models → Self-Owned AI Ecosystem
```

## Build phases (models)

| Phase | Name | Intent |
|------|------|--------|
| 1 | External Teacher Models | Limited strong teachers for hard work + high-quality training data |
| 2 | Internal Student Models | Train/specialize owned models on verified teacher outputs |
| 3 | Internal Model Optimization | Smaller, cheaper, broader internal coverage (LoRA/QLoRA/quant) |
| 4 | Self-Owned AI Ecosystem | Most work internal; external only for exceptional need |

## Target model family (from one base + LoRA)

| Internal model | Role |
|----------------|------|
| Internal Reasoning | Planning / decisions |
| Internal Coding | Implementation |
| Internal Project Intelligence | Codebase / architecture understanding |
| Internal Vision | UI / design analysis |
| Internal Critic | Review of plans & code |
| Internal Embeddings | Semantic retrieval |

Start with **one multi-task base**, specialize with **LoRA adapters**; spawn full independent models only when results justify cost.

## Knowledge Transfer & Distillation Engine

Behavioral knowledge transfer (not weight cloning):

1. Hard task → external teacher  
2. Capture structured outputs  
3. Verify via tests / tools / independent critique  
4. Promote verified pairs to training data  
5. Tag by specialty  
6. Train / LoRA-update internal student  
7. Compare vs teacher + held-out eval  
8. Promote only on real improvement without regression  

Techniques used selectively: SFT, LoRA/QLoRA, distillation, DPO, quantization, synthetic data, continual evaluation.

## Intelligent Model Router (cost control)

| Mechanism | Rule |
|-----------|------|
| Local First | Try internal before teacher |
| Prefer Promoted | When a specialty LoRA is promoted, raise trust and skip teacher escalate |
| Confidence Routing | Escalate on low evidence / tool failure — not model self-score alone |
| Caching | Deduplicate repeated prompts/results |
| Batching | Group similar teacher calls |
| Selective Distillation | Turn expensive recurring teacher work into student training fuel |

Default: **buy no capability we already own.** Replace a teacher with a student only after quality gates pass. Track **cost per successful task**.

## Project long-term memory (handoff fuel)

Owned agents must learn *and remember* per project:

- Every user/assistant utterance is appended to `{workspace}/memory/transcript.jsonl` and a `conversation` knowledge node.
- Standing instructions (`remember` / `احفظ` / …) become durable `decision` nodes.
- Hard isolation: never read another project's transcript; binding always includes workspace + isolation namespace.
- When promoted internals cover the specialty, teachers stay escalate-only — the goal is full handoff to owned agents.

## Fast ownership handoff (Phase 22)

Goal: students learn **extremely fast**, then teachers leave the critical path.

1. Successful chat / Chief outcomes → verified distillation examples (`evolve/chat_outcome`)
2. Standing instructions + transcript pairs → project-bound fuel
3. Readiness map: specialty is `handoff_ready` when **promoted** and has ≥ `lora_min_examples`
4. Ready specialties use `teacher_policy=escalate_only` under prefer-promoted routing

APIs: `GET /system/ownership/handoff`, `POST /system/ownership/handoff/distill-project`.

## Measured coverage + retirement (Phases 28–33)

- Persist router metrics; climb via `POST /system/ownership/coverage/climb` (`mode=meter|live`)
- Auto-retire teachers when specialties are `handoff_ready` (`AUTO_RETIRE_READY_TEACHERS`)
- Real LoRA: `LORA_REAL_TRAIN_ENABLED` → `training/real_lora.py` (tiny-gpt2 fallback)
- Live alerts: `NOTIFICATION_WEBHOOK_URL` (+ email) for مساعد الطيار reports

## Learn from everything + Autopilot (Phase 23)

- **Successes and mistakes** both enter `ExperienceJournal` and distillation (failures become “what not to repeat + corrective approach”).
- **Intake advisory:** after a project is understood, the agent explains engineering structure and drafts improvement/risk proposals (human-gated).
- **مساعد الطيار:** before leaving, enable Autopilot. It copies each project into an experimental sandbox, analyzes there only, then emails/queues a full report (why / risks / fixes). Originals stay untouched until you approve.

## Continuous Model Learning

Fail → classify (tool vs data vs train) → teacher only if needed → verify → train candidate → held-out eval → promote or discard. Cadence daily/weekly — not after every task.

## Implementation track in Evolve

See `docs/PHASES.md` § Ownership track.

| Package | Role |
|---------|------|
| `backend/app/gateway/` | Teachers, internal family, Intelligent Router, host probe |
| `backend/app/distillation/` | Verified teacher→JSONL (+ PI seed from scanners) |
| `backend/app/eval/` | Held-out teacher vs student compare + promote gates |
| `backend/app/training/` | LoRA job manifests/adapters (real GPU train optional) |

**Promotion rule:** adapter `promoted=true` only when eval gates pass (parity vs teacher, min score, not stub). Placeholder adapters never auto-promote.

Host check: `scripts/check-internal-host.ps1` or `GET /system/ownership/host`.

## Chief Agent (general lead)

The owned student brain is the **ChiefAgent** runtime:

- Chief assigns every subordinate task.
- Workers live in a pool (coding / reasoning / critic / …).
- When **all workers are busy**, Chief **spawns** a new worker, **fast-trains** it (curriculum seed + LoRA prepare, eval deferred), and **assigns** the waiting task.
- Chat still enters via `MasterOrchestrator`; dispatch goes through `ChiefOrchestra` when `CHIEF_ENABLED=true`.

APIs: `GET /system/chief`, `POST /system/chief/assign`, `POST /system/chief/spawn`, `POST /system/chief/demo/saturate`.

**Fast eval model:** held-out promote gates use `INTERNAL_EVAL_MODEL_NAME` (e.g. `qwen2.5:0.5b`) with lower `max_tokens`/timeout so Chief's heavy base (`INTERNAL_MODEL_NAME`) is not required for every gate. Successful Chief worker outcomes can distill when `CHIEF_DISTILL_OUTCOMES=true`.
