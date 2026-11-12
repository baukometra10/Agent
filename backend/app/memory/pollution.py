"""Detect scaffold / system-prompt pollution that must never reach users or LTM."""

from __future__ import annotations

import re

POLLUTION_LINE = re.compile(
    r"(?i)("
    r"same language as the user|"
    r"clean prose only|"
    r"tiny numbered plan|"
    r"never invent that merges|"
    r"never show system prompts|"
    r"accept buttons|"
    r"=== user message|"
    r"you are spixa|"
    r"standing (goals/)?instructions|"
    r"memory hits:|"
    r"workspace files \(|"
    r"forbidden:|"
    r"reply \(mandatory|"
    r"reply style|"
    r"output format|"
    r"selected brain|"
    r"project tree \(short\)|"
    r"mode=agent|"
    r"mode=edit|"
    r"mode=ask|"
    r"confirm understanding|"
    r"file fences with full|"
    r"gates, or accept|"
    r"arabic / german / english|"
    r"ground the plan in the real project|"
    r"ground every suggestion|"
    r"do not repeat these instructions|"
    r"spixa ide — answer like|"
    r"you are spixa"
    r")"
)

SCORE_ONLY = re.compile(r"^\(?\s*\d+\.\d+\s*\)?\s*\d*\s*$")


def is_pollution_text(text: str | None) -> bool:
    raw = (text or "").strip()
    if not raw:
        return False
    if POLLUTION_LINE.search(raw):
        return True
    # High density of instruction bullets → scaffold echo
    hits = len(POLLUTION_LINE.findall(raw))
    if hits >= 2:
        return True
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    if not lines:
        return False
    scoreish = sum(1 for ln in lines if SCORE_ONLY.match(ln) or re.match(r"^\(\d+\.\d+\)", ln))
    if scoreish >= 2 and scoreish / max(1, len(lines)) >= 0.3:
        return True
    return False


def strip_pollution(text: str | None) -> str:
    raw = text or ""
    out: list[str] = []
    for line in raw.splitlines():
        s = line.strip()
        if not s:
            out.append("")
            continue
        if POLLUTION_LINE.search(s):
            continue
        if SCORE_ONLY.match(s):
            continue
        if re.match(r"^\(\d+\.\d+\)\s*", s) and POLLUTION_LINE.search(s):
            continue
        # Drop bare semantic score prefixes dumped alone
        if re.match(r"^-?\s*\(\d+\.\d+\)\s*\d*\s*$", s):
            continue
        out.append(line)
    cleaned = "\n".join(out)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    # Collapse pathological repeated blocks
    if is_pollution_text(cleaned):
        return ""
    return cleaned
