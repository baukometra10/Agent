"""Smart code completion suggestions for the Spixa IDE."""

from __future__ import annotations

from typing import Any


def _line_prefix(prefix: str) -> str:
    if not prefix:
        return ""
    return prefix.rsplit("\n", 1)[-1]


def _heuristic_suggestions(
    *,
    language: str,
    prefix: str,
    suffix: str,
    path: str,
) -> list[dict[str, Any]]:
    line = _line_prefix(prefix)
    stripped = line.lstrip()
    indent = line[: len(line) - len(stripped)]
    lang = (language or "").lower()
    out: list[dict[str, Any]] = []

    def add(text: str, label: str) -> None:
        if text and text not in {s["insertText"] for s in out}:
            out.append({"insertText": text, "label": label})

    if lang in {"python", "py"}:
        if stripped.startswith("def ") and stripped.endswith(":"):
            add(f"\n{indent}    ", "function body")
        if stripped in {"if ", "elif ", "while ", "for "}:
            add(":", "colon")
        if stripped.startswith("print(") and not stripped.endswith(")"):
            add('")', "close print")
        if stripped == "im":
            add("port ", "import")
        if stripped == "from ":
            add("typing import Any", "typing Any")
        if stripped.endswith("try:"):
            add(f"\n{indent}    pass\n{indent}except Exception as exc:\n{indent}    raise", "try/except")
        if "main" in path and 'if __name__ == "__main__"' not in prefix:
            if stripped.startswith("if __name__"):
                add(' == "__main__":\n    main()', "main guard")
        if stripped.endswith("-> "):
            add("None:", "return None")
    elif lang in {"typescript", "javascript", "typescriptreact", "javascriptreact"}:
        if stripped.startswith("function ") and stripped.endswith("{"):
            add(f"\n{indent}  \n{indent}}}", "function body")
        if stripped.startswith("const ") and " = " not in stripped:
            add(" = ", "assign")
        if stripped.endswith("=>"):
            add(" {\n  \n}", "arrow block")
        if stripped == "con":
            add("sole.log()", "console.log")
        if stripped.endswith("console.log("):
            add(")", "close log")
        if stripped.startswith("import ") and " from " not in stripped and stripped.count("'") + stripped.count('"') == 1:
            add(" from '';", "from module")
        if stripped.endswith("async "):
            add("function ", "async function")
    elif lang in {"html"}:
        if stripped.endswith("<div"):
            add("></div>", "div pair")
        if stripped.endswith("<button"):
            add(' type="button"></button>', "button")
    elif lang in {"css", "scss"}:
        if stripped.endswith("{"):
            add(f"\n{indent}  \n{indent}}}", "rule body")

    # generic pair closers
    pairs = {"(": ")", "[": "]", "{": "}", '"': '"', "'": "'"}
    if stripped and stripped[-1] in pairs and not suffix.startswith(pairs[stripped[-1]]):
        add(pairs[stripped[-1]], f"close {stripped[-1]}")

    return out[:6]


async def suggest_completions(
    *,
    language: str,
    prefix: str,
    suffix: str = "",
    path: str = "",
) -> dict[str, Any]:
    """Return inline/completion candidates (gateway first, heuristics always as fallback)."""
    suggestions = _heuristic_suggestions(
        language=language,
        prefix=prefix[-4000:],
        suffix=suffix[:1000],
        path=path,
    )

    # Optional hosted/internal model boost for coding specialty
    try:
        from app.config import get_settings
        from app.gateway.internal import internal_chat

        settings = get_settings()
        if (settings.internal_model_base_url or "").strip() and len(prefix.strip()) >= 8:
            prompt = (
                "Complete the next few tokens of this code. "
                "Return ONLY the completion text to insert at the cursor, no markdown.\n\n"
                f"File: {path or 'unknown'} ({language})\n"
                f"PREFIX:\n{prefix[-2000:]}\n"
                f"SUFFIX:\n{suffix[:400]}\n"
            )
            text, _, _, _, stubbed = await internal_chat(
                settings=settings,
                model_id="internal/coding",
                prompt=prompt,
                system="You are Spixa inline coder. Output only code to insert.",
                timeout=8.0,
                max_tokens=64,
            )
            if not stubbed:
                insert = (text or "").strip()
                if insert.startswith("```"):
                    lines = insert.split("\n")
                    if lines and lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines and lines[-1].strip() == "```":
                        lines = lines[:-1]
                    insert = "\n".join(lines)
                insert = insert.strip("\n")
                if insert and len(insert) < 400:
                    suggestions.insert(0, {"insertText": insert, "label": "Spixa AI"})
    except Exception:  # noqa: BLE001 — completions must never break the editor
        pass

    # de-dupe
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for s in suggestions:
        key = s.get("insertText") or ""
        if key in seen:
            continue
        seen.add(key)
        unique.append(s)
    return {"ok": True, "suggestions": unique[:8]}
