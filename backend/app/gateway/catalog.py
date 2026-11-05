"""Curated chief-model catalog — Spixa + OpenRouter teachers (one upstream)."""

from __future__ import annotations

from typing import Any


# Spixa-owned brains (local / internal family)
SPIXA_MODELS: list[dict[str, Any]] = [
    {
        "id": "internal",
        "label": "Spixa Internal",
        "group": "spixa",
        "tier": "Owned",
        "detail": "العقل المملوك — يُفضَّل تلقائياً عند الجاهزية",
        "provider": "internal",
    },
]

# External teachers — all reachable via OpenRouter with a single key.
# Slugs follow OpenRouter's author/model form (OpenAI-compatible).
OPENROUTER_TEACHERS: list[dict[str, Any]] = [
    {
        "id": "openai/gpt-4.1",
        "label": "GPT-4.1",
        "group": "other",
        "tier": "High",
        "detail": "OpenAI via OpenRouter",
        "provider": "openrouter",
    },
    {
        "id": "openai/gpt-4.1-mini",
        "label": "GPT-4.1 Mini",
        "group": "other",
        "tier": "Fast",
        "detail": "OpenAI via OpenRouter",
        "provider": "openrouter",
    },
    {
        "id": "openai/gpt-4o",
        "label": "GPT-4o",
        "group": "other",
        "tier": "Medium",
        "detail": "OpenAI via OpenRouter",
        "provider": "openrouter",
    },
    {
        "id": "anthropic/claude-sonnet-4.5",
        "label": "Claude Sonnet 4.5",
        "group": "other",
        "tier": "High",
        "detail": "Anthropic via OpenRouter",
        "provider": "openrouter",
    },
    {
        "id": "anthropic/claude-opus-4.5",
        "label": "Claude Opus 4.5",
        "group": "other",
        "tier": "High",
        "detail": "Anthropic via OpenRouter",
        "provider": "openrouter",
    },
    {
        "id": "anthropic/claude-3.5-sonnet",
        "label": "Claude 3.5 Sonnet",
        "group": "other",
        "tier": "High",
        "detail": "Anthropic via OpenRouter",
        "provider": "openrouter",
    },
    {
        "id": "google/gemini-2.5-pro",
        "label": "Gemini 2.5 Pro",
        "group": "other",
        "tier": "Medium",
        "detail": "Google via OpenRouter",
        "provider": "openrouter",
    },
    {
        "id": "x-ai/grok-3",
        "label": "Grok 3",
        "group": "other",
        "tier": "Fast",
        "detail": "xAI via OpenRouter",
        "provider": "openrouter",
    },
    {
        "id": "deepseek/deepseek-chat",
        "label": "DeepSeek Chat",
        "group": "other",
        "tier": "Fast",
        "detail": "DeepSeek via OpenRouter",
        "provider": "openrouter",
    },
]


def chief_catalog(*, openrouter_configured: bool = False) -> dict[str, Any]:
    """Cursor-style chief picker payload for the IDE."""
    return {
        "upstream": "openrouter",
        "upstream_note": (
            "معلّمون خارجيون عبر منبع واحد (OpenRouter). "
            "عند جاهزية Spixa Internal يُفضَّل تلقائياً لتقليل التكلفة."
        ),
        "openrouter_configured": openrouter_configured,
        "auto": {
            "id": "auto",
            "label": "Auto",
            "detail": "داخلي أولاً → تصعيد للمعلّم عند الحاجة → تقطير للملكية",
        },
        "groups": [
            {
                "id": "spixa",
                "label": "Spixa Models",
                "models": SPIXA_MODELS,
            },
            {
                "id": "other",
                "label": "Other Models",
                "models": OPENROUTER_TEACHERS,
            },
        ],
        "models": [
            {"id": "auto", "label": "Auto", "group": "auto", "tier": "", "provider": "auto"},
            *SPIXA_MODELS,
            *OPENROUTER_TEACHERS,
        ],
    }


def resolve_chief_choice(choice: str | None) -> dict[str, Any]:
    """Normalize UI choice → routing hints for the gateway."""
    raw = (choice or "").strip()
    low = raw.lower()
    if not raw or low in {"auto", "automatic", "cursor", "cursor_class"}:
        return {"mode": "auto", "preferred_provider": None, "preferred_model": None}
    if low in {"internal", "spixa", "local", "spixa-internal", "spixa_internal"}:
        return {"mode": "internal", "preferred_provider": "internal", "preferred_model": None}
    if low in {"openrouter", "upstream"}:
        return {"mode": "teacher", "preferred_provider": "openrouter", "preferred_model": None}
    if low in {"openai", "gpt", "chatgpt"}:
        return {
            "mode": "teacher",
            "preferred_provider": "openrouter",
            "preferred_model": "openai/gpt-4.1",
        }
    if low in {"anthropic", "claude"}:
        return {
            "mode": "teacher",
            "preferred_provider": "openrouter",
            "preferred_model": "anthropic/claude-sonnet-4.5",
        }
    # Full slug: openai/gpt-4.1, anthropic/claude-opus-4.5, …
    if "/" in raw:
        return {
            "mode": "teacher",
            "preferred_provider": "openrouter",
            "preferred_model": raw,
        }
    return {"mode": "auto", "preferred_provider": None, "preferred_model": None}
