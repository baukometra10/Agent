"""Project autonomy policy.

The agent is highly independent for understand / analyze / plan / draft.
Execution, merge, and deploy remain human-gated unless explicitly enabled.
"""

from __future__ import annotations

from typing import Any

DEFAULT_AUTONOMY = {
    "auto_understand": True,
    "auto_analyze": True,
    "auto_plan": True,
    "auto_draft_proposals": True,
    "auto_execute": False,
    "auto_merge": False,
    "auto_deploy": False,
}


def autonomy_of(project_settings: dict[str, Any] | None) -> dict[str, bool]:
    settings = project_settings or {}
    raw = settings.get("autonomy") if isinstance(settings, dict) else None
    merged = dict(DEFAULT_AUTONOMY)
    if isinstance(raw, dict):
        for key, value in raw.items():
            if key in merged:
                merged[key] = bool(value)
    return merged


def may_execute(project_settings: dict[str, Any] | None) -> bool:
    return autonomy_of(project_settings)["auto_execute"]


def may_plan(project_settings: dict[str, Any] | None) -> bool:
    return autonomy_of(project_settings)["auto_plan"]


def may_draft_proposals(project_settings: dict[str, Any] | None) -> bool:
    return autonomy_of(project_settings)["auto_draft_proposals"]


def may_deploy(project_settings: dict[str, Any] | None) -> bool:
    return autonomy_of(project_settings)["auto_deploy"]
