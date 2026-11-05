"""Curated verified seeds for Internal Embeddings (retrieval / semantic similarity)."""

from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings
from app.distillation.engine import DistillationEngine, get_distillation_engine


EMBEDDINGS_SEED_PAIRS: tuple[dict[str, str], ...] = (
    {
        "prompt": "When should Evolve use owned embeddings instead of an external embedding API?",
        "output": (
            "Use owned embeddings for project-local retrieval, memory graph search, and recurring "
            "similarity inside isolated workspaces. Escalate to external embeddings only for "
            "cross-lingual edge cases or when held-out retrieval quality gates fail."
        ),
    },
    {
        "prompt": "How do we keep embedding stores project-isolated?",
        "output": (
            "Store vectors under the project workspace/namespace only. Never share an embeddings "
            "index across projects. Include isolation namespace in every index key and reject "
            "cross-workspace queries at the retrieval boundary."
        ),
    },
    {
        "prompt": "Describe a minimal retrieval pipeline for project long-term memory.",
        "output": (
            "Chunk transcript and knowledge nodes, embed with the internal embeddings student, "
            "retrieve top-k by cosine similarity, then re-rank with critic/reasoning for "
            "provenance before injecting into the prompt."
        ),
    },
    {
        "prompt": "What signals mean an embeddings specialty is handoff_ready?",
        "output": (
            "Promoted adapter, enough verified distill examples, held-out retrieval keywords pass, "
            "and teacher policy moves to escalate_only / retired so Local First serves semantic search."
        ),
    },
    {
        "prompt": "Compare keyword search vs embeddings for code symbol lookup.",
        "output": (
            "Keywords excel at exact symbols and file paths. Embeddings help when intent is "
            "paraphrased (find auth middleware). Prefer hybrid: filter by path/language then "
            "rank remaining chunks with owned embeddings."
        ),
    },
)


def seed_embeddings_curriculum(
    *,
    settings: Settings | None = None,
    engine: DistillationEngine | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    engine = engine or get_distillation_engine()
    accepted = 0
    ids: list[str] = []
    for pair in EMBEDDINGS_SEED_PAIRS:
        result = engine.ingest_teacher_output(
            role="embedding",
            prompt=pair["prompt"],
            system="You are Internal Embeddings. Explain retrieval, isolation, and hybrid search clearly.",
            teacher_model="evolve/curated-embeddings-curriculum",
            teacher_output=pair["output"],
            metadata={
                "specialty": "embeddings",
                "distill": True,
                "tools_ok": True,
                "human_verified": True,
            },
        )
        if result.get("accepted"):
            accepted += 1
            ids.append(str(result.get("id")))
    return {
        "specialty": "embeddings",
        "accepted": accepted,
        "ids": ids,
        "seed_pairs": len(EMBEDDINGS_SEED_PAIRS),
    }
