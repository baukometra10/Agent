"""Live agent activity bus — feeds the interactive brain UI."""

from __future__ import annotations

import itertools
import threading
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import UUID


@dataclass
class ActivityEvent:
    id: int
    ts: float
    kind: str  # think | tool | code | decision | status | memory | neural
    title: str
    detail: str = ""
    project_id: str | None = None
    project_name: str | None = None
    agent: str = "Spixa"
    intensity: float = 0.5  # 0..1 for neural viz
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ActivityBus:
    def __init__(self, maxlen: int = 500) -> None:
        self._events: deque[ActivityEvent] = deque(maxlen=maxlen)
        self._lock = threading.Lock()
        self._seq = itertools.count(1)
        self._focus: dict[str, Any] = {
            "project_id": None,
            "project_name": None,
            "phase": "idle",
            "resume_hint": None,
            "last_user_message": None,
            "active": False,
            "updated_at": time.time(),
        }

    def emit(
        self,
        kind: str,
        title: str,
        *,
        detail: str = "",
        project_id: UUID | str | None = None,
        project_name: str | None = None,
        agent: str = "Spixa",
        intensity: float = 0.55,
        payload: dict[str, Any] | None = None,
        set_focus: bool = True,
    ) -> ActivityEvent:
        event = ActivityEvent(
            id=next(self._seq),
            ts=time.time(),
            kind=kind,
            title=title,
            detail=detail,
            project_id=str(project_id) if project_id else None,
            project_name=project_name,
            agent=agent,
            intensity=max(0.0, min(1.0, intensity)),
            payload=payload or {},
        )
        with self._lock:
            self._events.append(event)
            if set_focus and project_id:
                self._focus.update(
                    {
                        "project_id": str(project_id),
                        "project_name": project_name or self._focus.get("project_name"),
                        "phase": kind,
                        "active": kind not in {"status"} or intensity > 0.2,
                        "updated_at": event.ts,
                    }
                )
                if kind == "memory" and detail:
                    self._focus["resume_hint"] = detail
                if payload and payload.get("user_message"):
                    self._focus["last_user_message"] = payload["user_message"]
        return event

    def set_idle(self, *, hint: str | None = None) -> None:
        with self._lock:
            self._focus["active"] = False
            self._focus["phase"] = "idle"
            self._focus["updated_at"] = time.time()
            if hint:
                self._focus["resume_hint"] = hint

    def since(self, after_id: int = 0, *, project_id: str | None = None, limit: int = 80) -> list[dict[str, Any]]:
        with self._lock:
            items = list(self._events)
        out: list[dict[str, Any]] = []
        for ev in items:
            if ev.id <= after_id:
                continue
            if project_id and ev.project_id and ev.project_id != project_id:
                continue
            out.append(ev.to_dict())
        return out[-limit:]

    def recent(self, *, limit: int = 40, project_id: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            items = list(self._events)
        out = [
            ev.to_dict()
            for ev in items
            if not project_id or not ev.project_id or ev.project_id == project_id
        ]
        return out[-limit:]

    def focus(self) -> dict[str, Any]:
        with self._lock:
            # Auto-idle if no events for 12s
            focus = dict(self._focus)
            if focus.get("active") and time.time() - float(focus.get("updated_at") or 0) > 12:
                focus["active"] = False
                focus["phase"] = "idle"
            return focus

    def snapshot(self, *, project_id: str | None = None) -> dict[str, Any]:
        return {
            "focus": self.focus(),
            "events": self.recent(limit=50, project_id=project_id),
            "server_time": time.time(),
        }


_BUS: ActivityBus | None = None
_BUS_LOCK = threading.Lock()


def get_activity_bus() -> ActivityBus:
    global _BUS
    with _BUS_LOCK:
        if _BUS is None:
            _BUS = ActivityBus()
            _BUS.emit(
                "status",
                "Spixa online",
                detail="Activity bus ready — waiting for agent work",
                intensity=0.15,
                set_focus=False,
            )
        return _BUS
