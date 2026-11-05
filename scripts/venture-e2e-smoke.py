"""Smoke: create venture → approve through gates (uses live API).

  cd backend
  ..\\.venv\\Scripts\\python.exe ..\\scripts\\venture-e2e-smoke.py
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

API = "http://127.0.0.1:7000"
BRIEF = (
    "أريد منظومة لإدارة شركة تتكيف مع التوسع وتكتشف الاختناقات وتقترح تحسينات مستمرة"
)


def req(method: str, path: str, body: dict | None = None, timeout: int = 600):
    data = None if body is None else json.dumps(body).encode("utf-8")
    r = urllib.request.Request(
        API + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if body is not None else {},
    )
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    projects = req("GET", "/api/projects", timeout=30)
    if not projects:
        print("FAIL: no projects")
        return 1
    pid = projects[0]["id"]
    print("project", pid, projects[0].get("name"))

    # Schema / patterns
    patterns = req("GET", "/api/patterns", timeout=30)
    print("patterns", len(patterns.get("patterns") or []))

    twin = req("POST", f"/api/projects/{pid}/twin/rebuild", timeout=120)
    print("twin components", twin.get("component_count"), "layers", len(twin.get("layers") or []))

    sim = req(
        "POST",
        f"/api/projects/{pid}/twin/simulate",
        {"change_summary": BRIEF, "affected_paths": [".spixa/design", "api"]},
        timeout=60,
    )
    print("sim blast", sim.get("blast_count"), "risk", sim.get("risk_score"), sim.get("recommendation"))

    print("creating venture (may take a few minutes)...")
    try:
        venture = req(
            "POST",
            f"/api/projects/{pid}/ventures",
            {"brief": BRIEF, "title": "E2E smoke Firmen-OS"},
            timeout=900,
        )
    except urllib.error.HTTPError as exc:
        print("FAIL create", exc.code, exc.read()[:500])
        return 1

    print(
        "venture",
        venture.get("id"),
        venture.get("status"),
        venture.get("current_phase"),
        [p.get("name") + ":" + p.get("status") for p in venture.get("phases") or []],
    )

    gates = 0
    while venture.get("status") == "awaiting_approval" and gates < 6:
        gates += 1
        vid = venture["id"]
        selected = venture.get("selected_architecture_id")
        phase = next(
            (p for p in venture.get("phases") or [] if p.get("status") == "awaiting_approval"),
            None,
        )
        if phase and phase.get("name") == "architecture":
            alts = ((phase.get("output") or {}).get("evolution") or {}).get("alternatives") or []
            if alts:
                selected = alts[0].get("id") or selected
        print("approve gate", gates, phase.get("name") if phase else "?")
        try:
            venture = req(
                "POST",
                f"/api/projects/{pid}/ventures/{vid}/approve",
                {
                    "actor": "e2e",
                    "selected_architecture_id": selected,
                    "acknowledge_adversarial": True,
                },
                timeout=900,
            )
        except urllib.error.HTTPError as exc:
            print("FAIL approve", exc.code, exc.read()[:500])
            return 1
        print("  ->", venture.get("status"), venture.get("current_phase"))

    print("DONE", venture.get("status"), "gates", gates)
    return 0 if venture.get("status") in {"completed", "awaiting_approval", "running"} else 1


if __name__ == "__main__":
    sys.exit(main())
