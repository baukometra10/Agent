"""Internal base-model host readiness (OpenAI-compatible: Ollama / vLLM / llama.cpp)."""

from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings, get_settings


async def probe_internal_host(settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    base = (settings.internal_model_base_url or "").strip().rstrip("/")
    if not base:
        return {
            "configured": False,
            "reachable": False,
            "models": [],
            "advice": (
                "Set INTERNAL_MODEL_BASE_URL to an OpenAI-compatible server "
                "(e.g. http://127.0.0.1:11434 for Ollama, or vLLM :8000)."
            ),
        }

    headers: dict[str, str] = {}
    key = (settings.internal_model_api_key or "").strip()
    if key:
        headers["Authorization"] = f"Bearer {key}"

    models: list[str] = []
    reachable = False
    error: str | None = None
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            # Try OpenAI /v1/models then Ollama /api/tags
            try:
                res = await client.get(f"{base}/v1/models", headers=headers)
            except Exception:
                res = None
            if res is not None and res.status_code < 400:
                reachable = True
                data = res.json()
                for row in data.get("data") or []:
                    mid = row.get("id")
                    if mid:
                        models.append(str(mid))
            else:
                res2 = await client.get(f"{base}/api/tags", headers=headers)
                if res2.status_code < 400:
                    reachable = True
                    data = res2.json()
                    for row in data.get("models") or []:
                        name = row.get("name") or row.get("model")
                        if name:
                            models.append(str(name))
                elif res is not None:
                    error = f"HTTP {res.status_code}: {res.text[:200]}"
                else:
                    error = f"HTTP {res2.status_code}: {res2.text[:200]}"
    except Exception as exc:  # noqa: BLE001
        error = str(exc)

    preferred = (settings.internal_model_name or "").strip()
    eval_model = (settings.internal_eval_model_name or "").strip()
    preferred_present = bool(preferred) and any(preferred in m for m in models)
    eval_present = bool(eval_model) and any(eval_model in m for m in models)

    return {
        "configured": True,
        "base_url": base,
        "reachable": reachable,
        "models": models[:50],
        "preferred_model": preferred or None,
        "preferred_present": preferred_present if preferred else None,
        "eval_model": eval_model or None,
        "eval_model_present": eval_present if eval_model else None,
        "error": error,
        "ready_for_local_first": reachable and (preferred_present if preferred else bool(models) or True),
        "advice": None
        if reachable
        else "Host not reachable. Start Ollama (`ollama serve`) or vLLM, then re-probe.",
    }
