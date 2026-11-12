"""Extract the real user ask from IDE scaffold / mode wrappers."""

from __future__ import annotations


def extract_user_topic(text: str) -> str:
    """Pull the real user ask out of IDE scaffold / mode wrappers."""
    raw = text or ""
    for marker in (
        "=== USER MESSAGE (reply in this language) ===",
        "=== USER MESSAGE ===",
        "طلب المستخدم:",
        "User request:",
        "User:",
        "طلب المستخدم",
    ):
        if marker in raw:
            raw = raw.split(marker)[-1]
            break
    lines: list[str] = []
    for line in raw.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("[mode:"):
            continue
        if s.startswith("أنت وكيل") or s.startswith("العقل الرئيس"):
            continue
        if s.startswith("You are the Spixa") or s.startswith("You are Spixa") or s.startswith(
            "LANGUAGE (mandatory)"
        ):
            continue
        if s.startswith("Spixa IDE") or s.startswith("WORKFLOW every turn"):
            continue
        if s.startswith("After UI/web") or s.startswith("Live Preview"):
            continue
        if s.startswith("وضع الوكيل") or s.startswith("وضع السؤال") or s.startswith("وضع التعديل"):
            continue
        if s.startswith("Mode=agent") or s.startswith("Mode=ask") or s.startswith("Mode=edit"):
            continue
        if s.startswith("Execution first") or s.startswith("When creating or editing"):
            continue
        if s.startswith("Build / site") or s.startswith("Ask clarifying"):
            continue
        if s.startswith("شجرة المشروع") or s.startswith("ملف مفتوح") or s.startswith("لا ملف"):
            continue
        if s.startswith("Project tree") or s.startswith("Selected brain") or s.startswith(
            "Linked file"
        ):
            continue
        if s.startswith("No file open") or s.startswith("Attachments:"):
            continue
        if s.startswith("الطلب يبدو") or s.startswith("عدّل فقط"):
            continue
        if s.startswith("User clearly asked") or s.startswith("Prefer improving"):
            continue
        if s.startswith("User wants a new project") or s.startswith("Reply ONLY"):
            continue
        if s.startswith("### ") or s.startswith("```"):
            continue
        lines.append(s)
    return " ".join(lines).strip() or (text or "").strip()
