# Rapid Learning System — منظومة التعلم السريع

**Doctrine:** Internal Intelligence First. External teachers seed students; Distillation Engine is core, not optional.

## Seven linked layers

1. **External teachers** — hard tasks only (coding / reasoning / critic / vision teachers)
2. **Knowledge extraction** — solutions, strategies, errors, lessons
3. **Training data factory** — verified, diverse corpora
4. **Specialized train & distill** — SFT, LoRA/QLoRA, KD (DPO/RL later by eval need)
5. **Competitive eval lab** — held-out domains; never train on eval cases
6. **Improve & retrain** — close weaknesses; ship better releases
7. **Continual cycle** — each release seeds the next

## Multi-teacher

Limited strong teachers by specialty. On disagreement: sandbox tests + tools + independent critic decide the winner. Always respect provider licenses before distillation.

## Multi-Agent Learning Lab

Coder → Reviewer → Security → Tester → Architect → Coordinator. Learn from successes **and** failures/fixes.

## Execution-verified learning

Write → isolated run → tests → analyze → repair → independent review → promote only verified outcomes.

## APIs

- `GET /system/learning/rapid` — blueprint
- `POST /system/learning/rapid/cycle` — continual cycle
- `POST /system/learning/rapid/competitive` — competitive snapshot
- `POST /system/learning/lab/multi-agent` — multi-agent lab session
- `POST /system/learning/lab/execution-verified` — promote from real runs
