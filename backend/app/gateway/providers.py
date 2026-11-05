"""Live model provider adapters (OpenAI + Anthropic) via httpx."""

from __future__ import annotations

from typing import Any

import httpx


class ProviderError(RuntimeError):
    def __init__(self, provider: str, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.provider = provider
        self.status = status


def strip_model_id(model_id: str) -> tuple[str, str]:
    """Return (provider, bare_model). Defaults provider to openai when omitted."""
    if "/" in model_id:
        provider, bare = model_id.split("/", 1)
        return provider.lower(), bare
    return "openai", model_id


async def openai_chat(
    *,
    api_key: str,
    model: str,
    prompt: str,
    system: str | None = None,
    timeout: float = 90.0,
) -> tuple[str, int, int, dict[str, Any]]:
    messages: list[dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {"model": model, "messages": messages, "temperature": 0.2}
    async with httpx.AsyncClient(timeout=timeout) as client:
        res = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=body,
        )
    if res.status_code >= 400:
        raise ProviderError("openai", res.text[:800], status=res.status_code)
    data = res.json()
    content = (data.get("choices") or [{}])[0].get("message", {}).get("content") or ""
    usage = data.get("usage") or {}
    return (
        content,
        int(usage.get("prompt_tokens") or 0),
        int(usage.get("completion_tokens") or 0),
        data,
    )


async def openai_embed(
    *,
    api_key: str,
    model: str,
    prompt: str,
    timeout: float = 60.0,
) -> tuple[str, int, int, dict[str, Any]]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {"model": model, "input": prompt[:8000]}
    async with httpx.AsyncClient(timeout=timeout) as client:
        res = await client.post(
            "https://api.openai.com/v1/embeddings",
            headers=headers,
            json=body,
        )
    if res.status_code >= 400:
        raise ProviderError("openai", res.text[:800], status=res.status_code)
    data = res.json()
    vec = (data.get("data") or [{}])[0].get("embedding") or []
    usage = data.get("usage") or {}
    return (
        f"[embedding dims={len(vec)}]",
        int(usage.get("prompt_tokens") or 0),
        0,
        {"dims": len(vec), "usage": usage},
    )


async def anthropic_chat(
    *,
    api_key: str,
    model: str,
    prompt: str,
    system: str | None = None,
    timeout: float = 90.0,
) -> tuple[str, int, int, dict[str, Any]]:
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    body: dict[str, Any] = {
        "model": model,
        "max_tokens": 4096,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    async with httpx.AsyncClient(timeout=timeout) as client:
        res = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=body,
        )
    if res.status_code >= 400:
        raise ProviderError("anthropic", res.text[:800], status=res.status_code)
    data = res.json()
    parts = data.get("content") or []
    text_chunks = [p.get("text", "") for p in parts if p.get("type") == "text"]
    content = "".join(text_chunks)
    usage = data.get("usage") or {}
    return (
        content,
        int(usage.get("input_tokens") or 0),
        int(usage.get("output_tokens") or 0),
        data,
    )


async def openrouter_chat(
    *,
    api_key: str,
    model: str,
    prompt: str,
    system: str | None = None,
    base_url: str = "https://openrouter.ai/api/v1",
    site_url: str = "https://spixa.local",
    app_name: str = "Spixa",
    timeout: float = 90.0,
) -> tuple[str, int, int, dict[str, Any]]:
    """Unified teacher upstream — one key reaches GPT/Claude/Gemini/Grok/…"""
    messages: list[dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": site_url or "https://spixa.local",
        "X-OpenRouter-Title": app_name or "Spixa",
    }
    body = {"model": model, "messages": messages, "temperature": 0.2}
    url = f"{base_url.rstrip('/')}/chat/completions"
    async with httpx.AsyncClient(timeout=timeout) as client:
        res = await client.post(url, headers=headers, json=body)
    if res.status_code >= 400:
        raise ProviderError("openrouter", res.text[:800], status=res.status_code)
    data = res.json()
    content = (data.get("choices") or [{}])[0].get("message", {}).get("content") or ""
    usage = data.get("usage") or {}
    return (
        content,
        int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0),
        int(usage.get("completion_tokens") or usage.get("output_tokens") or 0),
        data,
    )
