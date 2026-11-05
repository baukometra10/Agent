"""Speech transcription with automatic language detection (Whisper)."""

from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings


class SpeechError(RuntimeError):
    pass


async def transcribe_audio(
    *,
    settings: Settings,
    filename: str,
    content_type: str,
    data: bytes,
) -> dict[str, Any]:
    """Transcribe speech. Language is auto-detected by Whisper (no lang required)."""
    if not data:
        raise SpeechError("empty_audio")

    openrouter_key = (settings.openrouter_api_key or "").strip()
    openai_key = (settings.openai_api_key or "").strip()
    use_or = (settings.teacher_upstream or "openrouter").strip().lower() == "openrouter" and bool(openrouter_key)

    if use_or:
        return await _whisper_multipart(
            url=f"{settings.openrouter_base_url.rstrip('/')}/audio/transcriptions",
            api_key=openrouter_key,
            model="openai/whisper-1",
            filename=filename,
            content_type=content_type,
            data=data,
            extra_headers={
                "HTTP-Referer": settings.openrouter_site_url or "https://spixa.local",
                "X-OpenRouter-Title": settings.openrouter_app_name or "Spixa",
            },
            provider="openrouter",
        )

    if openai_key:
        return await _whisper_multipart(
            url="https://api.openai.com/v1/audio/transcriptions",
            api_key=openai_key,
            model="whisper-1",
            filename=filename,
            content_type=content_type,
            data=data,
            extra_headers={},
            provider="openai",
        )

    raise SpeechError("missing_speech_upstream")


async def _whisper_multipart(
    *,
    url: str,
    api_key: str,
    model: str,
    filename: str,
    content_type: str,
    data: bytes,
    extra_headers: dict[str, str],
    provider: str,
) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {api_key}", **extra_headers}
    # Omit `language` so Whisper auto-detects the spoken language.
    files = {"file": (filename or "speech.webm", data, content_type or "audio/webm")}
    form = {"model": model, "response_format": "verbose_json"}
    async with httpx.AsyncClient(timeout=90.0) as client:
        res = await client.post(url, headers=headers, files=files, data=form)
    if res.status_code >= 400:
        raise SpeechError(f"{provider}:{res.status_code}:{res.text[:400]}")
    payload = res.json()
    text = str(payload.get("text") or "").strip()
    language = payload.get("language")
    return {
        "text": text,
        "language": language,
        "provider": provider,
        "model": model,
        "duration": payload.get("duration"),
    }


def speech_status(settings: Settings) -> dict[str, Any]:
    openrouter_ok = bool((settings.openrouter_api_key or "").strip())
    openai_ok = bool((settings.openai_api_key or "").strip())
    use_or = (settings.teacher_upstream or "openrouter").strip().lower() == "openrouter" and openrouter_ok
    return {
        "auto_language": True,
        "upstream": "openrouter" if use_or else ("openai" if openai_ok else None),
        "live": bool(use_or or openai_ok),
        "note": "Whisper auto-detects spoken language; no manual language pick.",
    }
