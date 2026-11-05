"""Apply experimental patches inside مساعد الطيار sandbox only.

Produces unified diffs + suggestion files. Never receives the original workspace path
as a write target — callers must pass the sandbox clone.
"""

from __future__ import annotations

import difflib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.autopilot.markers import require_sandbox_marker


def _assert_sandbox(sandbox: Path) -> Path:
    sandbox = sandbox.resolve()
    require_sandbox_marker(sandbox)
    return sandbox


def _write_tracked(path: Path, content: str, *, sandbox: Path) -> dict[str, Any]:
    path = path.resolve()
    if not str(path).startswith(str(sandbox.resolve())):
        raise PermissionError(f"Patch path escapes sandbox: {path}")
    before = path.read_text(encoding="utf-8") if path.exists() else ""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    after = content
    rel = str(path.relative_to(sandbox)).replace("\\", "/")
    diff = "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=f"a/{rel}",
            tofile=f"b/{rel}",
        )
    )
    return {"path": rel, "created": not before, "diff": diff, "bytes": len(after.encode("utf-8"))}


def apply_experimental_patches(
    sandbox: Path,
    *,
    project_name: str,
    review: dict[str, Any],
    advisory: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Mutate sandbox only; return patch manifest + combined diff."""
    sandbox = _assert_sandbox(sandbox)
    advisory = advisory or {}
    applied: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc).isoformat()

    suggestions_dir = sandbox / "evolve-sandbox"
    suggestions_dir.mkdir(parents=True, exist_ok=True)

    # 1) Always write a human-readable experiment brief inside sandbox
    brief_lines = [
        f"# مساعد الطيار — تجربة لـ {project_name}",
        "",
        f"generated_at: {now}",
        "",
        "هذه الملفات داخل نسخة تجريبية فقط. لم تُلمس الأصول.",
        "",
        "## لماذا",
        (advisory.get("message_ar") or "مراجعة جودة وأمن وتحسينات مقترحة."),
        "",
        "## أمن",
    ]
    for row in (review.get("security") or [])[:10]:
        brief_lines.append(f"- [{row.get('severity')}] {row.get('title')}: {row.get('recommendation')}")
    brief_lines += ["", "## مخاطر"]
    for row in (review.get("risks") or [])[:10]:
        brief_lines.append(f"- [{row.get('severity')}] {row.get('title')}: {row.get('recommendation')}")
    brief_lines += ["", "## تحسينات"]
    for row in (review.get("improvements") or [])[:10]:
        brief_lines.append(f"- {row.get('title')}: {row.get('recommendation')}")
    brief_lines += [
        "",
        "## بوابة بشرية",
        "وافق على المقترح في Spixa قبل أي تطبيق على المشروع الأصلي.",
        "",
    ]
    applied.append(
        _write_tracked(
            suggestions_dir / "SUGGESTIONS.md",
            "\n".join(brief_lines) + "\n",
            sandbox=sandbox,
        )
    )

    # 2) Harden .gitignore experimentally if secrets risk or .env present
    titles = " ".join(
        str(x.get("title") or "")
        for x in (review.get("security") or []) + (review.get("risks") or [])
    )
    if ".env" in titles.lower() or "سر" in titles or "env" in titles.lower():
        gi = sandbox / ".gitignore"
        existing = gi.read_text(encoding="utf-8") if gi.exists() else ""
        needed = [".env", ".env.*", "*.pem", "secrets/", ".spixa-sandbox", ".evolve-sandbox"]
        add = [line for line in needed if line not in existing.splitlines()]
        if add:
            new = existing.rstrip() + ("\n" if existing and not existing.endswith("\n") else "")
            new += "\n# evolve مساعد الطيار (تجريبي)\n" + "\n".join(add) + "\n"
            applied.append(_write_tracked(gi, new, sandbox=sandbox))

    # 3) Placeholder smoke test if none detected
    improvements = " ".join(str(i.get("title") or "") for i in (review.get("improvements") or []))
    if "اختبارات" in improvements:
        test_path = sandbox / "tests" / "test_evolve_smoke_placeholder.py"
        content = (
            '"""Placeholder smoke test proposed by مساعد الطيار (sandbox only)."""\n\n'
            "def test_evolve_smoke_placeholder():\n"
            "    assert True\n"
        )
        applied.append(_write_tracked(test_path, content, sandbox=sandbox))

    combined = "\n".join(a["diff"] for a in applied if a.get("diff")).strip()
    diff_path = suggestions_dir / "experiment.diff"
    if combined:
        applied.append(_write_tracked(diff_path, combined + "\n", sandbox=sandbox))

    # Manifest last so it lists every patched file (including itself + diff)
    file_rows = [{"path": a["path"], "created": a["created"], "bytes": a["bytes"]} for a in applied]
    file_rows.append(
        {
            "path": "evolve-sandbox/manifest.json",
            "created": True,
            "bytes": 0,
        }
    )
    manifest = {
        "generated_at": now,
        "project_name": project_name,
        "originals_touched": False,
        "files": file_rows,
        "review_counts": {
            "security": len(review.get("security") or []),
            "risks": len(review.get("risks") or []),
            "improvements": len(review.get("improvements") or []),
        },
    }
    manifest_body = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    file_rows[-1]["bytes"] = len(manifest_body.encode("utf-8"))
    applied.append(
        _write_tracked(suggestions_dir / "manifest.json", manifest_body, sandbox=sandbox)
    )

    return {
        "ok": True,
        "originals_touched": False,
        "files_changed": [a["path"] for a in applied],
        "patch_count": len(applied),
        "combined_diff": combined[:20000],
        "diff_path": str(diff_path) if combined else None,
        "manifest_path": str(suggestions_dir / "manifest.json"),
        "suggestions_path": str(suggestions_dir / "SUGGESTIONS.md"),
    }
