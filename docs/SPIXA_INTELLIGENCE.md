# Spixa Proprietary Intelligence Ecosystem

**Adopted strategic orientation.** Spixa is a family of specialized, owned AI models under your control, evolving continuously — not a thin wrapper around external APIs.

## Thought transfer (local)

`POST /system/ownership/seed/thought-transfer` seeds the **Spixa Engineering Method**
(evidence → smallest change → verify → human gates) into specialty corpora and expands via synthetic factory.
Runtime internal chat also injects the method into the system prompt (Ollama path).
LoRA adapters may be trained locally on that corpus; loading PEFT into Ollama is a later serving step.

## Company doctrine (locked)

> Spixa is an **AI company that owns a family of specialized minds** — not merely a platform that rents others’ models.

Keep the platform foundation already built (phases 1–52). The **next chapter** centers on:

1. **Real training** (GPU LoRA/QLoRA on staging — deferred locally)  
2. **Independent evaluation** (maturity gates, held-out benches, independence probes)  
3. **Ownership of weights & data** (Ownership Registry + licensed corpora + adapters)  
4. **Proof on real engineering tasks** (sandbox execution, task success, human acceptance — not example counts)

External teachers remain temporary fuel. Production specialties ship only through factory + maturity gates.

## Priorities

1. Speed to advanced capability  
2. High engineering quality  
3. Ownership of weights, data, and training pipelines  
4. Lower operating and training cost  

## Non-goal (explicit)

**Training a huge foundation model from scratch is not a success condition.**  
We build an owned specialty family and pick the best technical path per specialty (shared base + adapters first; independent models only when justified). Full foundation independence remains an optional later stage.

Related: [MODEL_OWNERSHIP.md](./MODEL_OWNERSHIP.md) · [MODEL_FACTORY.md](./MODEL_FACTORY.md) · [RAPID_LEARNING.md](./RAPID_LEARNING.md)

---

## Six specialties + central orchestrator

| Product name | Specialty key (runtime) | Responsibility | Priority |
|--------------|-------------------------|----------------|----------|
| **Spixa Reasoner** | `reasoning` | Thinking, analysis, planning | Very high |
| **Spixa Coder** | `coding` | Write / edit / fix code | Critical |
| **Spixa Architect** | `project_intelligence` | Project understanding & architecture | Critical |
| **Spixa Critic** | `critic` | Independent review, risks, errors | High |
| **Spixa Vision** | `vision` | UI / design / image analysis | Medium |
| **Spixa Embed** | `embeddings` | Semantic search & knowledge retrieval | High |

**Spixa Intelligence Orchestrator** (Chief + Intelligent Router + Gateway): understand task → pick specialty → fan-out if needed → gather → independent critique → retry or ship. No random peer-to-peer model calls — unified protocol records task, results, cost, and versions.

Day-one architecture: **one open-weight base + LoRA/QLoRA adapters**. Split into fully separate models only when eval proves the cost is worth it.

---

## Eight technical layers

1. **Product** — Web · IDE · Desktop · API · Project Fleet  
2. **Intelligence Orchestrator** — task planning & agent/model coordination  
3. **Private Model Gateway** — routing · load · context · cost · entitlements  
4. **Specialty models** — Reasoner · Coder · Architect · Critic · Vision · Embed  
5. **Knowledge & Project Intelligence** — PostgreSQL · pgvector · KG · project memory  
6. **Learning & Training Factory** — distillation · synthetic · train · eval · human gates  
7. **Infrastructure & Governance** — GPU · storage · Docker · security · registry · monitoring  
8. *(Cross-cutting)* **Human approval** — no production weight/router mutation without gates  

Stack we keep unless evidence forces change: FastAPI · LangGraph · Ollama→vLLM/SGLang · PyTorch/PEFT/TRL · PostgreSQL/pgvector · Tree-sitter · pytest+held-out benches · MLflow (target) · DVC (target) · Docker · Next.js.

---

## What we own

| Owned | Notes |
|-------|--------|
| Training data we have rights to use | License documented per source |
| Synthetic data we produce | Via Synthetic Data Factory |
| Adapter weights we train | Primary near-term IP |
| Model releases we ship | Factory release IDs |
| Train/eval tooling & gateway | Spixa platform |
| Spixa engineering knowledge | Playbooks, corpora, graphs |

Adapter ownership ≠ automatic ownership of the **base** weights. Choose commercially usable open licenses; document each component. A fully private foundation model is a **later optional** program.

---

## Intelligence roadmap (on top of platform phases 1–51)

GPU/real-train proof remains deferred until private staging deploy (see operating rules).

| Phase | Name | Target | Focus |
|-------|------|--------|--------|
| **I1** | Real Training Foundation | 3–5 weeks | GPU LoRA/QLoRA · weight/adapter registry · pre/post eval · first approved adapter |
| **I2** | Spixa Coding Intelligence | 4–6 weeks | Coding corpus · Coder adapter · project edit/fix · sandbox · vs teacher |
| **I3** | Engineering Intelligence | 4–6 weeks | Reasoner + Architect · large-project understanding · memory↔analysis |
| **I4** | Quality Intelligence | 3–5 weeks | Critic · security/perf review · agent-output evaluation |
| **I5** | Model Collaboration | 4–6 weeks | Multi-specialty team protocols · team vs solo eval |
| **I6** | Continuous Evolution | 2–4 mo then ongoing | Execution learning · release trail · $/successful task · routing |

Do **not** redo platform phases 1–50; this roadmap consumes the factory, rapid learning, and ownership stack already landed.

---

## How we know a specialty is mature

**Not** by training-example count or adapter count.

Independent scorecard per specialty (`GET /system/intelligence/maturity`):

| Metric | Proves |
|--------|--------|
| Task Success Rate | Real task success |
| Benchmark Score | Capability vs teachers / absolute floor |
| Regression Rate | No loss of prior capability |
| Cost per Successful Task | True economics |
| Human Acceptance Rate | Expert acceptance |
| Generalization | Held-out / unseen projects |
| Safety & Reliability | No unsafe unverified applies |

**No specialty ships to production** until its gates pass (`factory approve` enforces this; `force=true` is staging-only).

## Three control systems

1. **Model Ownership Registry** — `GET /system/intelligence/ownership-registry`  
   Base source/license · data rights · adapter versions · train config · eval · approver  
2. **Model Independence Mode** — `POST /system/intelligence/independence/probe`  
   Clears teacher keys for the probe session and **executes** core-path checks  
3. **Intelligence Evolution Dashboard** — `GET /system/intelligence/evolution`  
   Per-specialty trail: improved/regressed skills, cost signals, vs prior & vs teacher
