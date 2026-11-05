"""Speech-to-text API — automatic language detection."""

from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.config import get_settings
from app.gateway.speech import SpeechError, speech_status, transcribe_audio

router = APIRouter(prefix="/system/speech", tags=["speech"])


@router.get("/status")
async def status():
    return speech_status(get_settings())


@router.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    settings = get_settings()
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty audio")
    if len(raw) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Audio too large")
    try:
        result = await transcribe_audio(
            settings=settings,
            filename=file.filename or "speech.webm",
            content_type=file.content_type or "audio/webm",
            data=raw,
        )
    except SpeechError as exc:
        msg = str(exc)
        if "missing_speech_upstream" in msg:
            raise HTTPException(
                status_code=503,
                detail="Speech upstream unavailable — set OPENROUTER_API_KEY or OPENAI_API_KEY",
            ) from exc
        raise HTTPException(status_code=502, detail=msg) from exc
    return result
