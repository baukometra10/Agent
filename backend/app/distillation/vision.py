"""Curated verified seeds for Internal Vision (UI/design analysis)."""

from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings
from app.distillation.engine import DistillationEngine, get_distillation_engine

VISION_SEED_PAIRS: tuple[dict[str, str], ...] = (
    {
        "prompt": "A landing page hero has five CTAs and three badge overlays on the image. Critique for first viewport clarity.",
        "output": (
            "Too many competing actions dilute the primary CTA. Remove badge overlays from hero media, "
            "keep one headline, one supporting line, and one primary CTA group. "
            "Hero should be full-bleed atmosphere, not a collage of chips."
        ),
    },
    {
        "prompt": "Suggest a tokenizable color system for a calm productivity app (not purple-on-white).",
        "output": (
            "Define CSS variables: --bg, --surface, --ink, --muted, --accent, --line. "
            "Prefer a deep slate background with a single warm accent (amber or teal), "
            "avoid default AI purple gradients and cream-serif terracotta clichés."
        ),
    },
    {
        "prompt": "Wireframe a settings page with profile + model gateway status. One job per section.",
        "output": (
            "Sections: (1) Profile — name/role/email only. "
            "(2) Model ownership — Local First KPIs and provider readiness. "
            "(3) Autonomy gates checklist. "
            "No cards in a decorative hero; interactive panels only where the user acts."
        ),
    },
    {
        "prompt": "RTL Arabic dashboard: what typography and layout rules matter most?",
        "output": (
            "Respect dir=rtl for chrome; keep code/IDs LTR. Use an expressive Arabic-capable display font "
            "for titles, readable body sizes, and avoid mirroring diagrams that encode LTR reading order. "
            "Primary actions stay reachable in the first viewport without dense chip rows."
        ),
    },
    {
        "prompt": "Review a UI that uses Inter everywhere with flat white cards. Improvement direction?",
        "output": (
            "Replace default Inter/system stack with purposeful display+body pairing. "
            "Add atmospheric background (subtle gradient/pattern) and a real product visual anchor. "
            "Reduce card chrome where borders/shadows do not aid interaction."
        ),
    },
)


def seed_vision_curriculum(
    *,
    settings: Settings | None = None,
    engine: DistillationEngine | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    engine = engine or get_distillation_engine()
    accepted = 0
    ids: list[str] = []
    for pair in VISION_SEED_PAIRS:
        result = engine.ingest_teacher_output(
            role="multimodal",
            prompt=pair["prompt"],
            system="You are Internal Vision. Critique UI/UX with concrete, brand-aware guidance.",
            teacher_model="evolve/curated-vision-curriculum",
            teacher_output=pair["output"],
            metadata={
                "specialty": "vision",
                "distill": True,
                "tools_ok": True,
                "human_verified": True,
            },
        )
        if result.get("accepted"):
            accepted += 1
            ids.append(str(result.get("id")))
    return {"pairs": len(VISION_SEED_PAIRS), "accepted": accepted, "ids": ids}
