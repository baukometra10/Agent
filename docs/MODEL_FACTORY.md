# Model Development Factory — مصنع تطوير النماذج

**Doctrine:** لا نبني طلابًا يقلّدون المعلّم فقط — نبني **مصنعًا** يطوّر النماذج الداخلية تحت رقابة واختبارات وموافقات.

**Hard rule:** لا تعديل لأوزان الإنتاج أو قواعد الـ Router تلقائيًا. المرشّح يمرّ: تحقق → تقييم مستقل → اقتراح → **موافقة بشرية** → إنتاج.

Related: [MODEL_OWNERSHIP.md](./MODEL_OWNERSHIP.md) · [RAPID_LEARNING.md](./RAPID_LEARNING.md)

---

## Five core engines (day-one)

| # | Engine | Responsibility | Code |
|---|--------|----------------|------|
| 1 | **AI Learning Engine** | دورة التعلم: جمع → تدريب مرشّح → اقتراح إصدار | `app/factory/orchestrator.py` + `learning/loop.py` + `learning/rapid_system.py` |
| 2 | **Knowledge Distillation Engine** | نقل سلوكي من المعلّم الخارجي بعد تحقق | `app/distillation/engine.py` |
| 3 | **Synthetic Data Factory** | توسيع بيانات موثّقة ومتنوعة (لا تُقبل بلا تحقق) | `app/factory/synthetic.py` |
| 4 | **AI Evaluation Lab** | قياس مستقل + مقارنة بالطالب/المعلّم | `app/eval/harness.py` + competitive lab |
| 5 | **Self-Improvement Engine** | يقترح تحسينات؛ لا يطبّق أوزان إنتاج وحده | `app/factory/self_improve.py` |

Orchestrator: `GET/POST /system/factory/*`

---

## Knowledge flow (teacher → owned specialist)

```
┌──────────────┐   hard task / escalate    ┌──────────────────┐
│ External     │ ─────────────────────────►│ Teacher output   │
│ Teacher      │                           └────────┬─────────┘
└──────────────┘                                    │
                                                    ▼
                                         ┌──────────────────────┐
                                         │ Verify (tests/tools/ │
                                         │ critic/human)        │
                                         └──────────┬───────────┘
                                                    │ fail → _pending only
                                                    ▼ pass
                                         ┌──────────────────────┐
                                         │ Distill train.jsonl  │
                                         │ (specialty tagged)   │
                                         └──────────┬───────────┘
                                                    │
                    ┌───────────────────────────────┼────────────────────┐
                    ▼                               ▼                    ▼
           Synthetic Factory              Learning Engine         Experience /
           (variants + checks)            (LoRA candidate)        execution lab
                    │                               │
                    └───────────────┬───────────────┘
                                    ▼
                         ┌─────────────────────┐
                         │ Evaluation Lab      │
                         │ held-out suite      │
                         │ student vs teacher  │
                         └──────────┬──────────┘
                                    │ gates fail → improve & retrain
                                    ▼ gates pass
                         ┌─────────────────────┐
                         │ Release PROPOSAL    │
                         │ status=pending      │
                         │ (NOT production)    │
                         └──────────┬──────────┘
                                    │ human approve
                                    ▼
                         ┌─────────────────────┐
                         │ Production adapter  │
                         │ + router prefer     │
                         │ internal specialty  │
                         └─────────────────────┘
```

---

## When is the student “better than the teacher”?

For specialty `S`, declare **teacher-parity / beat** only if **all** hold:

1. **Held-out only** — eval cases never in train/synthetic corpora.
2. **Absolute floor** — `student_score >= EVAL_MIN_STUDENT_SCORE`.
3. **Parity ratio** — `student_score >= teacher_score * EVAL_TEACHER_PARITY_RATIO` (when teacher ran).
4. **Not stub** — no simulated/placeholder student answers.
5. **Regression check** — no drop vs previous factory-approved release on same suite.
6. **Human approval** — `POST /system/factory/releases/{id}/approve`.

Passing (1–5) creates a **proposal**. Only (6) ships to production routing.

---

## Gate matrix

| Gate | Blocks |
|------|--------|
| Distill verify | Empty / error / stub / missing tools|tests evidence |
| Synthetic accept | Unverified generated rows |
| Train | Below `LORA_MIN_EXAMPLES` |
| Eval promote flag | Parity / absolute / stub |
| Factory proposal | Eval did not pass |
| Regression vs last approved | Candidate score drops beyond tolerance |
| **Human approve** | Auto weight/router mutation |
| Reject / rollback | Bad production behavior |

`FACTORY_REQUIRE_HUMAN_APPROVAL=true` (default): LoRA/`promote/all` mark adapters `pending_factory_approval` and open a release proposal — they do **not** set production `promoted` until `POST /system/factory/releases/{id}/approve`.

---

## Release states

`draft` → `eval_running` → `pending_approval` → `approved` | `rejected` → (`rolled_back`)

Self-Improvement Engine may emit `improvement_proposals` (data gaps, weak domains, technique suggestions). It **never** writes production adapter weights directly.

---

## APIs

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/system/factory/blueprint` | Five engines + flow + live status |
| POST | `/system/factory/cycle` | Full gated cycle (propose only) |
| POST | `/system/factory/synthetic` | Generate synthetic candidates |
| POST | `/system/factory/evaluate` | Evaluation Lab snapshot |
| POST | `/system/factory/self-improve` | Propose improvements (no prod mutate) |
| GET | `/system/factory/releases` | List release proposals |
| POST | `/system/factory/releases/{id}/approve` | Human ship to production |
| POST | `/system/factory/releases/{id}/reject` | Reject candidate |
| GET | `/system/factory/proof/stack` | GPU + peft/transformers readiness |
| POST | `/system/factory/proof/coding` | Practical proof: real LoRA → eval → proposal (/approve) |
| GET | `/system/factory/proof/improvement` | Successive-release score trail |

### Practical proof checklist

**Deferred by product decision:** real LoRA / GPU proof and production Coding train wait until the full app is deployed to a **private/staging server**, validated there, and only then considered for a public server. Local/dev keeps `LORA_REAL_TRAIN_ENABLED=false`.

When that staging host is ready:

1. `GET /system/factory/proof/stack` — packages + CUDA  
2. `POST /system/factory/proof/coding` with `real_train=true`  
3. Approve release (or `approve_if_gates_pass=true` for operator proof)  
4. Re-run proof → `GET /system/factory/proof/improvement` must show delta across releases  

Install train extras on the train host: `pip install -e ".[train]"` (+ CUDA torch wheel).

---

## Technique selection (by eval need)

| Technique | When |
|-----------|------|
| KD / SFT | Transfer verified teacher behavior |
| LoRA / QLoRA | Cheap specialty adapters |
| Synthetic Data | Cover gaps after competitive lab |
| DPO | Preference between verified winners |
| RL | Only with verifiable rewards (tests) |
| Continual | After approve; monitor forgetting |

Not all techniques from day one — Evaluation Lab decides what to unlock next.
