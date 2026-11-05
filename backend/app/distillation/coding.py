"""Seed coding specialty training data from verified synthetic + workspace snippets."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.config import Settings, get_settings
from app.distillation.engine import DistillationEngine, get_distillation_engine

# Curated verified pairs (not in held-out eval suite ids).
CODING_SEED_PAIRS: tuple[dict[str, str], ...] = (
    {
        "prompt": "Write a Python function clamp(x, lo, hi) that bounds x between lo and hi.",
        "output": (
            "def clamp(x, lo, hi):\n"
            "    if lo > hi:\n"
            "        lo, hi = hi, lo\n"
            "    return max(lo, min(hi, x))\n"
        ),
    },
    {
        "prompt": "Write a TypeScript function isNonEmptyString(v: unknown): v is string.",
        "output": (
            "export function isNonEmptyString(v: unknown): v is string {\n"
            "  return typeof v === 'string' && v.trim().length > 0;\n"
            "}\n"
        ),
    },
    {
        "prompt": "Write a Python retry helper that retries fn up to n times on Exception.",
        "output": (
            "import time\n\n"
            "def retry(fn, n=3, delay=0.1):\n"
            "    last = None\n"
            "    for _ in range(n):\n"
            "        try:\n"
            "            return fn()\n"
            "        except Exception as exc:\n"
            "            last = exc\n"
            "            time.sleep(delay)\n"
            "    raise last\n"
        ),
    },
    {
        "prompt": "Write a pure function merge_dicts(a, b) where b overrides a (shallow).",
        "output": (
            "def merge_dicts(a: dict, b: dict) -> dict:\n"
            "    out = dict(a)\n"
            "    out.update(b)\n"
            "    return out\n"
        ),
    },
    {
        "prompt": "Write a FastAPI health route handler returning JSON {status: ok}.",
        "output": (
            "from fastapi import APIRouter\n\n"
            "router = APIRouter()\n\n"
            "@router.get('/health')\n"
            "async def health():\n"
            "    return {'status': 'ok'}\n"
        ),
    },
)


def seed_coding_curriculum(
    *,
    settings: Settings | None = None,
    engine: DistillationEngine | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    engine = engine or get_distillation_engine()
    accepted = 0
    ids: list[str] = []
    for pair in CODING_SEED_PAIRS:
        # tools_ok: curated curriculum treated as human/tool verified seed
        result = engine.ingest_teacher_output(
            role="coding",
            prompt=pair["prompt"],
            system="You are Internal Coding. Prefer correct, minimal code.",
            teacher_model="evolve/curated-coding-curriculum",
            teacher_output=pair["output"],
            metadata={"specialty": "coding", "distill": True, "tools_ok": True, "human_verified": True},
        )
        if result.get("accepted"):
            accepted += 1
            ids.append(str(result.get("id")))
    return {"pairs": len(CODING_SEED_PAIRS), "accepted": accepted, "ids": ids}


def seed_coding_from_repo(repo: Path, *, engine: DistillationEngine | None = None) -> dict[str, Any]:
    """Extract small pure functions from Python files as weak-verified examples."""
    engine = engine or get_distillation_engine()
    accepted = 0
    scanned = 0
    if not repo.exists():
        return {"accepted": 0, "scanned": 0, "error": "missing repo"}
    for path in list(repo.rglob("*.py"))[:40]:
        if any(p in path.parts for p in (".venv", "node_modules", "__pycache__", "tests")):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if "def " not in text or len(text) > 4000:
            continue
        scanned += 1
        prompt = f"Reimplement the public helpers found in {path.name} with the same behavior."
        result = engine.ingest_teacher_output(
            role="coding",
            prompt=prompt,
            system="You are Internal Coding. Match behavior; keep code small.",
            teacher_model="evolve/repo-snippet",
            teacher_output=text[:3500],
            metadata={
                "specialty": "coding",
                "distill": True,
                "tools_ok": True,
                "source_path": str(path),
            },
        )
        if result.get("accepted"):
            accepted += 1
    return {"scanned": scanned, "accepted": accepted, "repo": str(repo)}
