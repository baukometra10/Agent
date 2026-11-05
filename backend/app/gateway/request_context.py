"""Per-request routing preferences (chief brain / model / worker)."""

from __future__ import annotations

from contextvars import ContextVar

# auto | internal | openrouter | openai | anthropic
preferred_provider: ContextVar[str | None] = ContextVar("preferred_provider", default=None)
# Full teacher slug when forcing a specific OpenRouter model: openai/gpt-4.1
preferred_model: ContextVar[str | None] = ContextVar("preferred_model", default=None)
preferred_worker: ContextVar[str | None] = ContextVar("preferred_worker", default=None)
# Budget / escalate gates for a single IDE tab turn
forbid_teacher: ContextVar[bool] = ContextVar("forbid_teacher", default=False)
force_internal_ctx: ContextVar[bool] = ContextVar("force_internal_ctx", default=False)


def set_preferred_provider(value: str | None) -> None:
    preferred_provider.set((value or "").strip().lower() or None)


def get_preferred_provider() -> str | None:
    return preferred_provider.get()


def set_preferred_model(value: str | None) -> None:
    preferred_model.set((value or "").strip() or None)


def get_preferred_model() -> str | None:
    return preferred_model.get()


def set_preferred_worker(value: str | None) -> None:
    preferred_worker.set((value or "").strip() or None)


def get_preferred_worker() -> str | None:
    return preferred_worker.get()


def set_forbid_teacher(value: bool) -> None:
    forbid_teacher.set(bool(value))


def get_forbid_teacher() -> bool:
    return bool(forbid_teacher.get())


def set_force_internal(value: bool) -> None:
    force_internal_ctx.set(bool(value))


def get_force_internal() -> bool:
    return bool(force_internal_ctx.get())
