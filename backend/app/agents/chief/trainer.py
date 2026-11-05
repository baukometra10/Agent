"""Fast train path when Chief spawns a new subordinate worker."""

from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings
from app.distillation.coding import seed_coding_curriculum
from app.distillation.coding_tutor import seed_coding_tutor
from app.distillation.critic import seed_critic_curriculum
from app.distillation.engine import DistillationEngine, get_distillation_engine
from app.distillation.reasoning import seed_reasoning_curriculum
from app.distillation.vision import seed_vision_curriculum
from app.training.lora import LoRATrainer, get_lora_trainer


async def fast_train_specialty(
    specialty: str,
    *,
    settings: Settings | None = None,
    engine: DistillationEngine | None = None,
    trainer: LoRATrainer | None = None,
) -> dict[str, Any]:
    """Seed curriculum (if thin) + prepare LoRA placeholder — optimized for spawn latency.

    Real GPU fine-tune stays optional; behavioral routing uses internal/{specialty}
    against the owned base model immediately after seed.
    """
    settings = settings or get_settings()
    engine = engine or get_distillation_engine()
    trainer = trainer or get_lora_trainer()

    seed_fn = {
        "coding": seed_coding_curriculum,
        "reasoning": seed_reasoning_curriculum,
        "critic": seed_critic_curriculum,
        "vision": seed_vision_curriculum,
    }.get(specialty)

    seeded = None
    count = trainer.dataset_count(specialty)
    if seed_fn and count < int(settings.lora_min_examples):
        seeded = seed_fn(settings=settings, engine=engine)
        if specialty == "coding":
            seed_coding_tutor(settings=settings, engine=engine)
        count = trainer.dataset_count(specialty)
    elif specialty == "coding" and count < int(settings.lora_min_examples) * 3:
        seeded = seed_coding_tutor(settings=settings, engine=engine)
        count = trainer.dataset_count(specialty)

    # Skip live eval on spawn — Chief needs the worker *now*; promote later via learning cycle
    train = await trainer.train_specialty(
        specialty,
        run_eval=False,
        force_placeholder=count < int(settings.lora_min_examples),
    )
    return {
        "specialty": specialty,
        "dataset_count": count,
        "seeded": seeded,
        "train_ok": bool(train.get("ok")),
        "adapter": (train.get("job") or {}).get("adapter"),
        "status": (train.get("job") or {}).get("status"),
        "mode": "fast_spawn",
        "note": (
            "Worker can serve immediately via Local-First internal specialty route; "
            "full eval/promote runs in continual learning cycle."
        ),
    }
