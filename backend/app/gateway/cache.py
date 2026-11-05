"""Prompt/result cache for Intelligent Model Router."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Any


@dataclass
class CacheEntry:
    content: str
    model_id: str
    tokens_in: int
    tokens_out: int
    created_at: float
    hits: int = 0


class ResponseCache:
    def __init__(self, ttl_seconds: int = 3600, max_entries: int = 2048) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._store: dict[str, CacheEntry] = {}

    @staticmethod
    def make_key(role: str, model_id: str, prompt: str, system: str | None) -> str:
        raw = f"{role}|{model_id}|{system or ''}|{prompt}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(self, key: str) -> CacheEntry | None:
        entry = self._store.get(key)
        if not entry:
            return None
        if time.time() - entry.created_at > self.ttl_seconds:
            self._store.pop(key, None)
            return None
        entry.hits += 1
        return entry

    def put(
        self,
        key: str,
        *,
        content: str,
        model_id: str,
        tokens_in: int = 0,
        tokens_out: int = 0,
    ) -> None:
        if len(self._store) >= self.max_entries:
            # Drop oldest
            oldest = min(self._store.items(), key=lambda kv: kv[1].created_at)
            self._store.pop(oldest[0], None)
        self._store[key] = CacheEntry(
            content=content,
            model_id=model_id,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            created_at=time.time(),
        )

    def stats(self) -> dict[str, Any]:
        return {
            "entries": len(self._store),
            "ttl_seconds": self.ttl_seconds,
            "hits": sum(e.hits for e in self._store.values()),
        }
