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


def _valid_cursor_repo_url(repo_url: str | None) -> str | None:
    """Only real GitHub/GitLab repo URLs — never Cursor dashboard / org roots."""
    cleaned = (repo_url or "").strip().rstrip("/")
    if not cleaned:
        return None
    low = cleaned.lower()
    if "cursor.com" in low or "openrouter.ai" in low:
        return None
    if low in {
        "https://github.com",
        "http://github.com",
        "https://gitlab.com",
        "http://gitlab.com",
    }:
        return None
    try:
        from urllib.parse import urlparse

        parsed = urlparse(cleaned)
        host = (parsed.hostname or "").lower()
        if host not in {"github.com", "www.github.com", "gitlab.com", "www.gitlab.com"}:
            return None
        path = (parsed.path or "").strip("/")
        # require org/repo (exactly two segments at minimum)
        parts = [p for p in path.split("/") if p]
        if len(parts) < 2:
            return None
        return f"{parsed.scheme or 'https'}://{host}/{parts[0]}/{parts[1]}"
    except Exception:  # noqa: BLE001
        return None


async def cursor_cloud_agent_chat(
    *,
    api_key: str,
    prompt: str,
    system: str | None = None,
    base_url: str = "https://api.cursor.com",
    repo_url: str | None = None,
    model_id: str | None = None,
    poll_timeout_seconds: float = 180.0,
    poll_interval_seconds: float = 3.0,
) -> tuple[str, int, int, dict[str, Any]]:
    """Cursor Cloud Agents API as a coding teacher (create → poll run.result).

    Not a chat-completions API — best for coding/implementation prompts.
    Auth: Bearer or Basic (key as username). We use Bearer.
    """
    import asyncio
    import time

    text = prompt
    if system:
        text = f"{system.strip()}\n\n---\n\n{prompt}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body: dict[str, Any] = {
        "prompt": {"text": text[:120_000]},
        "name": "Spixa teacher",
    }
    if model_id:
        body["model"] = {"id": model_id}
    cleaned_repo = _valid_cursor_repo_url(repo_url)
    if cleaned_repo:
        body["repos"] = [{"url": cleaned_repo}]

    root = base_url.rstrip("/")
    async with httpx.AsyncClient(timeout=60.0) as client:
        create = await client.post(f"{root}/v1/agents", headers=headers, json=body)
        # Bad/non-git CURSOR_DEFAULT_REPO_URL → retry once as repo-less chat teacher
        if (
            create.status_code >= 400
            and cleaned_repo
            and "repos" in body
            and any(
                token in (create.text or "").lower()
                for token in ("repository", "source control", "repos", "validation_error")
            )
        ):
            body.pop("repos", None)
            create = await client.post(f"{root}/v1/agents", headers=headers, json=body)
        if create.status_code >= 400:
            raise ProviderError("cursor", create.text[:800], status=create.status_code)
        created = create.json()
        agent = created.get("agent") if isinstance(created.get("agent"), dict) else created
        run = created.get("run") if isinstance(created.get("run"), dict) else {}
        agent_id = str(agent.get("id") or created.get("id") or "")
        run_id = str(
            run.get("id")
            or agent.get("latestRunId")
            or created.get("latestRunId")
            or ""
        )
        if not agent_id or not run_id:
            raise ProviderError(
                "cursor",
                f"missing agent/run id in create response: {str(created)[:400]}",
            )

        deadline = time.monotonic() + max(30.0, poll_timeout_seconds)
        last: dict[str, Any] = {}
        while time.monotonic() < deadline:
            poll = await client.get(
                f"{root}/v1/agents/{agent_id}/runs/{run_id}",
                headers=headers,
            )
            if poll.status_code >= 400:
                raise ProviderError("cursor", poll.text[:800], status=poll.status_code)
            last = poll.json()
            status = str(last.get("status") or "").upper()
            if status in {"FINISHED", "ERROR", "CANCELLED", "EXPIRED"}:
                break
            await asyncio.sleep(max(1.0, poll_interval_seconds))
        else:
            raise ProviderError("cursor", "poll timeout waiting for Cursor agent run")

        if str(last.get("status") or "").upper() != "FINISHED":
            raise ProviderError(
                "cursor",
                f"run ended with status={last.get('status')}: {str(last.get('result') or '')[:400]}",
            )
        content = str(last.get("result") or "").strip()
        if not content:
            content = "(Cursor agent finished with empty result text)"
        # Token usage not exposed — approximate from chars
        tin = max(1, len(text) // 4)
        tout = max(1, len(content) // 4)
        return content, tin, tout, {"agent_id": agent_id, "run_id": run_id, "run": last}

