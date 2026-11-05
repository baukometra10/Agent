"""Held-out eval cases — never used for training promotion blindly."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class EvalCase:
    id: str
    specialty: str
    prompt: str
    system: str
    expect_keywords: tuple[str, ...] = ()
    expect_any: tuple[str, ...] = ()
    weight: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)


# Project Intelligence first specialty suite (held-out).
PROJECT_INTEL_SUITE: tuple[EvalCase, ...] = (
    EvalCase(
        id="pi-arch-layers",
        specialty="project_intelligence",
        prompt=(
            "Given a FastAPI + Next.js monorepo with backend/app and frontend/app, "
            "list the primary architectural layers and how requests flow. Be concise."
        ),
        system="You are Internal Project Intelligence. Prefer structure over fluff.",
        expect_keywords=("api", "frontend", "backend"),
        expect_any=("layer", "route", "service", "component"),
    ),
    EvalCase(
        id="pi-isolation",
        specialty="project_intelligence",
        prompt=(
            "Explain why Evolve isolates each project with its own workspace and namespace. "
            "Name two risks of shared memory across projects."
        ),
        system="You are Internal Project Intelligence.",
        expect_keywords=("isolat", "workspace"),
        expect_any=("leak", "cross", "contaminat", "mix", "shared"),
    ),
    EvalCase(
        id="pi-stack-detect",
        specialty="project_intelligence",
        prompt=(
            "A repo has pyproject.toml, package.json, Dockerfile, and tree-sitter grammars. "
            "Infer the likely stack and what Project Intelligence should extract first."
        ),
        system="You are Internal Project Intelligence.",
        expect_keywords=("python", "node"),
        expect_any=("docker", "typescript", "javascript", "fastapi", "next"),
    ),
    EvalCase(
        id="pi-knowledge-kinds",
        specialty="project_intelligence",
        prompt=(
            "Distinguish fact vs inference vs unverified in a knowledge graph for a codebase. "
            "Give one example of each."
        ),
        system="You are Internal Project Intelligence.",
        expect_keywords=("fact", "inference"),
        expect_any=("unverified", "evidence", "source"),
    ),
)


CODING_SMOKE_SUITE: tuple[EvalCase, ...] = (
    EvalCase(
        id="code-add",
        specialty="coding",
        prompt="Write a Python function add(a, b) that returns the sum. Code only.",
        system="You are Internal Coding.",
        expect_keywords=("def", "add", "return"),
    ),
    EvalCase(
        id="code-clamp",
        specialty="coding",
        prompt="Write Python clamp(x, lo, hi). Code only.",
        system="You are Internal Coding.",
        expect_keywords=("def", "clamp", "return"),
        expect_any=("max", "min"),
    ),
    EvalCase(
        id="code-merge",
        specialty="coding",
        prompt="Write Python merge_dicts(a, b) shallow merge where b wins. Code only.",
        system="You are Internal Coding.",
        expect_keywords=("def", "return"),
        expect_any=("update", "dict"),
    ),
)


REASONING_SUITE: tuple[EvalCase, ...] = (
    EvalCase(
        id="reason-isolation",
        specialty="reasoning",
        prompt="Why must Evolve isolate project memory? One paragraph.",
        system="You are Internal Reasoning.",
        expect_keywords=("isolat",),
        expect_any=("leak", "cross", "contaminat", "shared", "workspace"),
    ),
    EvalCase(
        id="reason-escalate",
        specialty="reasoning",
        prompt="When should an internal student escalate to an external teacher?",
        system="You are Internal Reasoning.",
        expect_keywords=("escalat",),
        expect_any=("test", "tool", "fail", "confidence", "evidence"),
    ),
    EvalCase(
        id="reason-human-gate",
        specialty="reasoning",
        prompt="Should agents auto-merge to main? State Evolve's rule.",
        system="You are Internal Reasoning.",
        expect_keywords=("human",),
        expect_any=("approv", "gate", "merge", "deploy"),
    ),
)


CRITIC_SUITE: tuple[EvalCase, ...] = (
    EvalCase(
        id="critic-sqli",
        specialty="critic",
        prompt="Critique SQL built with f-strings from user input. Name the risk and fix.",
        system="You are Internal Critic.",
        expect_keywords=("inject",),
        expect_any=("parameter", "bound", "prepared", "placeholder"),
    ),
    EvalCase(
        id="critic-secret",
        specialty="critic",
        prompt="A PR commits .env with API keys. What should the critic require?",
        system="You are Internal Critic.",
        expect_keywords=("secret",),
        expect_any=("rotat", "gitignore", "block", "remov"),
    ),
    EvalCase(
        id="critic-rollback",
        specialty="critic",
        prompt="Deploy plan has no rollback. Approve or reject and why.",
        system="You are Internal Critic.",
        expect_keywords=("rollback",),
        expect_any=("reject", "risk", "high", "require"),
    ),
)


VISION_SUITE: tuple[EvalCase, ...] = (
    EvalCase(
        id="vision-hero",
        specialty="vision",
        prompt="Hero has five CTAs and badge overlays. What should change?",
        system="You are Internal Vision.",
        expect_keywords=("cta",),
        expect_any=("one", "primary", "overlay", "hero", "clutter"),
    ),
    EvalCase(
        id="vision-tokens",
        specialty="vision",
        prompt="Propose CSS color tokens for a calm app avoiding purple defaults.",
        system="You are Internal Vision.",
        expect_keywords=("token",),
        expect_any=("accent", "css", "--", "variable", "color"),
    ),
    EvalCase(
        id="vision-rtl",
        specialty="vision",
        prompt="Name two RTL Arabic UI rules for a dashboard.",
        system="You are Internal Vision.",
        expect_keywords=("rtl",),
        expect_any=("arabic", "dir", "ltr", "font"),
    ),
)

EMBEDDINGS_SUITE: tuple[EvalCase, ...] = (
    EvalCase(
        id="emb-isolation",
        specialty="embeddings",
        prompt="How do we keep embedding stores project-isolated?",
        system="You are Internal Embeddings.",
        expect_keywords=("isolat",),
        expect_any=("workspace", "namespace", "project", "never share"),
    ),
    EvalCase(
        id="emb-hybrid",
        specialty="embeddings",
        prompt="When is hybrid keyword + embeddings retrieval better than embeddings alone?",
        system="You are Internal Embeddings.",
        expect_keywords=("hybrid",),
        expect_any=("keyword", "symbol", "path", "exact"),
    ),
    EvalCase(
        id="emb-owned",
        specialty="embeddings",
        prompt="When should Evolve prefer owned embeddings over an external API?",
        system="You are Internal Embeddings.",
        expect_keywords=("own",),
        expect_any=("local", "project", "retriev", "memory"),
    ),
)


def suite_for(specialty: str) -> list[EvalCase]:
    if specialty in ("project_intelligence", "project-intelligence", "pi"):
        return list(PROJECT_INTEL_SUITE)
    if specialty == "coding":
        return list(CODING_SMOKE_SUITE)
    if specialty == "reasoning":
        return list(REASONING_SUITE)
    if specialty == "critic":
        return list(CRITIC_SUITE)
    if specialty == "vision":
        return list(VISION_SUITE)
    if specialty in ("embeddings", "embedding"):
        return list(EMBEDDINGS_SUITE)
    if specialty == "all":
        return (
            list(PROJECT_INTEL_SUITE)
            + list(CODING_SMOKE_SUITE)
            + list(REASONING_SUITE)
            + list(CRITIC_SUITE)
            + list(VISION_SUITE)
            + list(EMBEDDINGS_SUITE)
        )
    return list(PROJECT_INTEL_SUITE)


def score_answer(case: EvalCase, content: str) -> float:
    text = (content or "").lower()
    if not text.strip() or text.startswith("[provider-error"):
        return 0.0
    # Stub students get partial credit only — not promotion-worthy
    if "[internal-student:" in text or "[simulated:" in text:
        base = 0.15
    else:
        base = 0.35
    hits = 0
    need = len(case.expect_keywords) + (1 if case.expect_any else 0)
    if need == 0:
        return min(1.0, base + 0.2)
    for kw in case.expect_keywords:
        if kw.lower() in text:
            hits += 1
    any_hit = True
    if case.expect_any:
        any_hit = any(a.lower() in text for a in case.expect_any)
        if any_hit:
            hits += 1
    ratio = hits / need if need else 0.0
    return round(min(1.0, base + ratio * 0.65), 4)
