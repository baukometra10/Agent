"""Sandbox-only quality/security heuristics for مساعد الطيار.

Never writes outside the sandbox path. Returns findings for the human report.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".next",
    "dist",
    "build",
    ".evolve-sandbox",
    ".spixa-sandbox",
}

SECRET_HINT = re.compile(
    r"(api[_-]?key|secret|password|token|aws_access|private_key)\s*[=:]\s*['\"]?[A-Za-z0-9/+=_\-]{8,}",
    re.I,
)
TODO_HINT = re.compile(r"\b(TODO|FIXME|XXX|HACK)\b")
DEBUG_HINT = re.compile(r"\b(eval\(|exec\(|pickle\.loads|DEBUG\s*=\s*True)\b")


def review_sandbox(sandbox: Path, *, max_files: int = 400) -> dict[str, Any]:
    risks: list[dict[str, str]] = []
    improvements: list[dict[str, str]] = []
    security: list[dict[str, str]] = []
    files_seen = 0
    has_tests = False
    has_ci = False
    has_readme = False
    has_lock = False

    if not sandbox.exists():
        return {
            "risks": [{"title": "Sandbox missing", "severity": "high", "recommendation": "Re-run مساعد الطيار"}],
            "improvements": [],
            "security": [],
            "files_scanned": 0,
        }

    for path in sandbox.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        files_seen += 1
        name = path.name.lower()
        rel = str(path.relative_to(sandbox)).replace("\\", "/")

        if name.startswith("test_") or name.endswith("_test.py") or "/tests/" in f"/{rel}/":
            has_tests = True
        if name in {".github", "ci.yml", "ci.yaml"} or ".github/workflows" in rel:
            has_ci = True
        if name in {"readme.md", "readme.rst", "readme"}:
            has_readme = True
        if name in {"package-lock.json", "pnpm-lock.yaml", "yarn.lock", "poetry.lock", "uv.lock"}:
            has_lock = True

        if files_seen > max_files:
            continue
        if path.suffix.lower() not in {
            ".py",
            ".ts",
            ".tsx",
            ".js",
            ".jsx",
            ".env",
            ".yml",
            ".yaml",
            ".json",
            ".md",
            ".toml",
        }:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")[:80000]
        except OSError:
            continue

        if path.suffix == ".env" or name.endswith(".env"):
            security.append(
                {
                    "title": f"ملف بيئة في المساحة: {rel}",
                    "severity": "high",
                    "recommendation": "تأكد أن الأسرار غير مُلتزمة؛ استخدم مخزناً آمناً ولا تنسخها للإنتاج يدوياً.",
                }
            )
        if SECRET_HINT.search(text):
            security.append(
                {
                    "title": f"احتمال سرّ مكشوف في {rel}",
                    "severity": "critical",
                    "recommendation": "أزل المفاتيح الصلبة، استخدم متغيرات بيئة، وأدر مفتاحاً جديداً إن لزم.",
                }
            )
        if DEBUG_HINT.search(text):
            risks.append(
                {
                    "title": f"نمط خطِر أو DEBUG في {rel}",
                    "severity": "medium",
                    "recommendation": "أغلق DEBUG في الإنتاج وتجنب eval/exec على مدخلات غير موثوقة.",
                }
            )
        if TODO_HINT.search(text) and len(improvements) < 12:
            improvements.append(
                {
                    "title": f"ملاحظات TODO/FIXME في {rel}",
                    "severity": "low",
                    "recommendation": "حوّل الملاحظات ذات الأولوية إلى مقترحات قابلة للتنفيذ.",
                }
            )

    if not has_tests:
        improvements.append(
            {
                "title": "لا توجد اختبارات واضحة",
                "severity": "medium",
                "recommendation": "أضف اختبارات دخان للمسارات الحرجة قبل أي دمج.",
            }
        )
    if not has_ci:
        improvements.append(
            {
                "title": "لا يظهر مسار CI",
                "severity": "medium",
                "recommendation": "أضف سير عمل تحقق (lint/test) لتقليل مخاطر الدمج.",
            }
        )
    if not has_readme:
        improvements.append(
            {
                "title": "README ناقص",
                "severity": "low",
                "recommendation": "وثّق التشغيل المحلي والغرض والحدود الأمنية.",
            }
        )
    if not has_lock:
        risks.append(
            {
                "title": "لا يوجد ملف قفل للتبعيات",
                "severity": "medium",
                "recommendation": "ثبّت إصدارات التبعيات لتفادي انزلاق الإصدارات.",
            }
        )

    # Deduplicate by title
    def uniq(rows: list[dict[str, str]]) -> list[dict[str, str]]:
        seen: set[str] = set()
        out: list[dict[str, str]] = []
        for r in rows:
            t = r.get("title") or ""
            if t in seen:
                continue
            seen.add(t)
            out.append(r)
        return out

    return {
        "files_scanned": files_seen,
        "security": uniq(security)[:12],
        "risks": uniq(risks)[:12],
        "improvements": uniq(improvements)[:12],
    }
