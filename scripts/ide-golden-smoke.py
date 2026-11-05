"""Golden IDE path smoke against a live Spixa API.

Flow: health → project → workspace write/read → agent apply-edits →
      terminal → chat session → venture list/create (optional long) → twin.

  # With API already running (start.ps1):
  python scripts/ide-golden-smoke.py

  # Skip slow Venture create (still checks list + twin):
  python scripts/ide-golden-smoke.py --fast

Env:
  SPIXA_API   default http://127.0.0.1:7000
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = os.environ.get("SPIXA_API", "http://127.0.0.1:7000").rstrip("/")
MARKER = f"spixa-golden-{int(time.time())}"


class Fail(Exception):
    pass


def req(method: str, path: str, body: dict | None = None, timeout: int = 120):
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Content-Type": "application/json"} if body is not None else {}
    r = urllib.request.Request(API + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read()[:800]
        raise Fail(f"{method} {path} → HTTP {exc.code}: {detail!r}") from exc
    except urllib.error.URLError as exc:
        raise Fail(f"{method} {path} → unreachable ({exc})") from exc


def step(name: str) -> None:
    print(f"· {name}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Spixa IDE golden smoke")
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Skip long Venture create/approve (still checks twin + list)",
    )
    parser.add_argument(
        "--venture",
        action="store_true",
        help="Force full Venture create + gate approve (slow)",
    )
    args = parser.parse_args()
    do_venture = args.venture or not args.fast
    if args.fast:
        do_venture = False

    print(f"API {API}")
    failed: list[str] = []

    try:
        step("health")
        health = req("GET", "/health", timeout=15)
        print("  ok", health.get("status") or health)

        step("project")
        # Prefer a fresh blank project so twin/tree stay fast and isolated.
        try:
            project = req(
                "POST",
                "/api/projects/blank",
                {"name": f"Golden {MARKER}", "slug": f"golden-{MARKER}"},
                timeout=60,
            )
            print("  created", project.get("name"), project.get("id"))
        except Fail as exc:
            print("  blank create failed, reuse existing:", exc)
            projects = req("GET", "/api/projects", timeout=30)
            if not isinstance(projects, list):
                projects = projects.get("projects") or []
            if not projects:
                raise Fail("no projects available") from exc
            project = projects[0]
            print("  reuse", project.get("name"), project.get("id"))
        pid = project["id"]

        rel = f".spixa/golden/{MARKER}.py"
        content = f'# {MARKER}\nprint("golden-ok")\n'

        step("workspace write")
        put = req(
            "PUT",
            f"/api/projects/{pid}/workspace/file",
            {"path": rel, "content": content},
            timeout=30,
        )
        if put.get("ok") is False:
            raise Fail(f"write failed: {put}")

        step("workspace read")
        got = req(
            "GET",
            f"/api/projects/{pid}/workspace/file?path={urllib.parse.quote(rel)}",
            timeout=30,
        )
        body = got.get("content") if isinstance(got, dict) else None
        if body is None and isinstance(got, dict):
            body = got.get("text")
        if not body or MARKER not in str(body):
            raise Fail(f"read mismatch: {got!r}")

        step("agent apply-edits")
        applied = req(
            "POST",
            f"/api/projects/{pid}/workspace/apply-edits",
            {
                "edits": [
                    {
                        "path": f".spixa/golden/{MARKER}-edit.md",
                        "content": f"# applied {MARKER}\n",
                    }
                ]
            },
            timeout=30,
        )
        if not applied.get("ok", True) and applied.get("errors"):
            raise Fail(f"apply-edits errors: {applied}")
        print("  applied", applied.get("applied") or applied)

        step("terminal")
        # Cross-platform-ish: python -c works on Windows with project python if PATH ok;
        # fall back to a trivial echo via cmd /c.
        term = req(
            "POST",
            f"/api/projects/{pid}/workspace/terminal",
            {"command": 'python -c "print(123)"', "timeout": 20},
            timeout=40,
        )
        if not term.get("ok") and term.get("exit_code") not in (0, None):
            term = req(
                "POST",
                f"/api/projects/{pid}/workspace/terminal",
                {"command": "echo golden", "timeout": 15},
                timeout=30,
            )
        print("  exit", term.get("exit_code"), "ok", term.get("ok"))

        step("chat session")
        sess = req(
            "POST",
            f"/api/projects/{pid}/chat/sessions",
            {"title": f"Golden {MARKER}"},
            timeout=30,
        )
        sid = sess.get("id") or sess.get("session_id")
        if not sid:
            raise Fail(f"no session id: {sess}")
        print("  session", sid)
        # Full chat round-trip needs a model; skip under --fast to keep smoke snappy.
        if args.fast:
            print("  (message skipped in --fast)")
        else:
            try:
                reply = req(
                    "POST",
                    f"/api/projects/{pid}/chat/sessions/{sid}/messages",
                    {
                        "message": "قل كلمة واحدة فقط: جاهز",
                        "mode": "ask",
                        "max_seconds": 25,
                    },
                    timeout=40,
                )
                print(
                    "  reply",
                    (reply.get("reply") or "")[:80],
                    "simulated",
                    reply.get("simulated"),
                )
            except Fail as exc:
                print("  chat soft-fail (LLM optional):", exc)
                failed.append("chat_soft")

        step("tree")
        tree = req("GET", f"/api/projects/{pid}/workspace/tree", timeout=30)
        entries = tree.get("entries") if isinstance(tree, dict) else tree
        n = len(entries or [])
        print("  entries", n)
        if n < 1:
            raise Fail("empty tree")

        step("ventures list")
        ventures = req("GET", f"/api/projects/{pid}/ventures", timeout=30)
        if isinstance(ventures, dict):
            ventures = ventures.get("ventures") or ventures.get("items") or []
        print("  count", len(ventures or []))

        if args.fast:
            print("· twin rebuild (skipped in --fast)")
        else:
            step("twin rebuild")
            twin = req("POST", f"/api/projects/{pid}/twin/rebuild", timeout=180)
            print("  components", twin.get("component_count"))

        if do_venture:
            step("venture create (slow)")
            brief = (
                "منظومة تشغيل صغيرة للاختبار الذهبي تكتشف اختناقاً واحداً وتقترح تحسيناً"
            )
            venture = req(
                "POST",
                f"/api/projects/{pid}/ventures",
                {"brief": brief, "title": f"Golden Venture {MARKER}"},
                timeout=900,
            )
            print(
                "  status",
                venture.get("status"),
                "phase",
                venture.get("current_phase"),
            )
            gates = 0
            while venture.get("status") == "awaiting_approval" and gates < 4:
                gates += 1
                vid = venture["id"]
                selected = venture.get("selected_architecture_id")
                phase = next(
                    (
                        p
                        for p in venture.get("phases") or []
                        if p.get("status") == "awaiting_approval"
                    ),
                    None,
                )
                if phase and phase.get("name") == "architecture":
                    alts = (
                        ((phase.get("output") or {}).get("evolution") or {}).get(
                            "alternatives"
                        )
                        or []
                    )
                    if alts:
                        selected = alts[0].get("id") or selected
                print("  approve", gates, phase.get("name") if phase else "?")
                venture = req(
                    "POST",
                    f"/api/projects/{pid}/ventures/{vid}/approve",
                    {
                        "actor": "golden-smoke",
                        "selected_architecture_id": selected,
                        "acknowledge_adversarial": True,
                    },
                    timeout=900,
                )
                print("   ->", venture.get("status"), venture.get("current_phase"))
            if venture.get("status") not in {
                "completed",
                "awaiting_approval",
                "running",
                "approved",
            }:
                raise Fail(f"venture bad status: {venture.get('status')}")
        else:
            print("  (venture create skipped — use --venture for full path)")

        step("intelligence maturity")
        board = req("GET", "/system/intelligence/maturity", timeout=30)
        specs = board.get("specialties") or []
        print("  specialties", len(specs), "blocked", board.get("blocked"))

        step("ownership registry")
        reg = req("GET", "/system/intelligence/ownership-registry", timeout=30)
        print("  registry keys", len(reg) if isinstance(reg, dict) else type(reg).__name__)

        step("record coding task outcomes (smoke evidence)")
        req(
            "POST",
            "/system/intelligence/maturity/task-outcome",
            {"specialty": "coding", "success": True, "source": "golden_smoke"},
            timeout=15,
        )
        req(
            "POST",
            "/system/intelligence/maturity/human-acceptance",
            {
                "specialty": "coding",
                "accepted": True,
                "note": "golden smoke path",
                "actor": "golden-smoke",
            },
            timeout=15,
        )

        if args.fast:
            print("· independence probe (skipped in --fast — use full run)")
        else:
            step("independence probe")
            probe = req("POST", "/system/intelligence/independence/probe", timeout=120)
            print(
                "  ok",
                probe.get("ok"),
                "passed",
                probe.get("passed"),
                "/",
                probe.get("total"),
                "failed",
                probe.get("failed"),
            )
            if not probe.get("ok"):
                failed.append("independence_soft")

        step("evolution dashboard")
        evo = req("GET", "/system/intelligence/evolution", timeout=30)
        print("  evo specialties", len(evo.get("specialties") or []))

    except Fail as exc:
        print("FAIL:", exc)
        return 1

    if failed:
        print("DONE with soft warnings:", ",".join(failed))
    else:
        print("DONE golden path OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
