"""Audit Railway env vars without printing secret values."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_AGENT = [
    "DATABASE_URL",
    "DATABASE_URL_SYNC",
    "SECRET_KEY",
    "APP_ENV",
    "WORKSPACES_ROOT",
    "TEACHER_UPSTREAM",
    "OPENROUTER_API_KEY",
    "PREFER_INTERNAL",
    "FAST_HANDOFF_ENABLED",
    "LEARN_FROM_EVERYTHING",
    "DISTILLATION_ENABLED",
    "CLOUD_WORKSPACES",
]

RECOMMENDED_AGENT = [
    "APP_NAME",
    "OPENROUTER_SITE_URL",
    "OPENROUTER_APP_NAME",
    "OPENROUTER_BASE_URL",
    "DISTILLATION_DATA_ROOT",
    "LEARNING_DATA_ROOT",
    "EVAL_DATA_ROOT",
    "TRAINING_ARTIFACTS_ROOT",
    "MODEL_GATEWAY_FORCE_SIMULATE",
    "ALLOW_UNTRUSTED_CODE_EXECUTION",
    "SANDBOX_NETWORK_DISABLED",
    "AUTO_RETIRE_READY_TEACHERS",
    "PREFER_PROMOTED_INTERNAL",
    "PROMOTED_NO_ESCALATE",
    "CHIEF_ENABLED",
    "CHIEF_DISTILL_OUTCOMES",
    "LORA_REAL_TRAIN_ENABLED",
    "EVOLUTION_CRON_ENABLED",
    "SUPER_ADMIN_EMAIL",
    "DEFAULT_CODING_MODEL",
    "DEFAULT_REASONING_MODEL",
    "DEFAULT_FAST_MODEL",
    "DEFAULT_CRITIC_MODEL",
    "CURSOR_API_KEY",
    "CURSOR_DEFAULT_REPO_URL",
]

WEB_REQUIRED = ["NEXT_PUBLIC_API_URL"]
CURRENT_AGENT_HOST = "agent-production-5cb5.up.railway.app"


def railway_vars(service: str) -> dict[str, str]:
    proc = subprocess.run(
        ["railway", "variable", "list", "--service", service, "--json"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        print("ERROR fetching", service, proc.stderr[:400], file=sys.stderr)
        return {}
    data = json.loads(proc.stdout or "{}")
    if isinstance(data, dict) and "variables" in data:
        data = data["variables"]
    if isinstance(data, list):
        return {(x.get("name") or x.get("key")): (x.get("value") or "") for x in data}
    if isinstance(data, dict):
        return {str(k): "" if v is None else str(v) for k, v in data.items()}
    return {}


def redact(k: str, v: str) -> str:
    if v is None or v == "":
        return "EMPTY"
    secretish = any(
        x in k.upper()
        for x in ("KEY", "SECRET", "PASSWORD", "TOKEN", "DATABASE", "URL", "CREDENTIAL")
    )
    if secretish:
        if v.startswith("${{"):
            return v
        return f"SET(len={len(v)})"
    return v if len(v) <= 90 else v[:87] + "..."


def main() -> int:
    agent = railway_vars("Agent")
    web = railway_vars("web")
    user_agent = {k: v for k, v in agent.items() if not str(k).startswith("RAILWAY_")}
    user_web = {k: v for k, v in web.items() if not str(k).startswith("RAILWAY_")}

    print("=== AGENT (custom) ===")
    for k in sorted(user_agent):
        print(f"  {k}={redact(k, user_agent[k])}")

    print("\n=== WEB (custom) ===")
    for k in sorted(user_web):
        print(f"  {k}={redact(k, user_web[k])}")

    print("\n=== REQUIRED AGENT ===")
    missing = []
    for k in REQUIRED_AGENT:
        v = (agent.get(k) or "").strip()
        ok = bool(v)
        # soft: CURSOR not required
        if k == "OPENROUTER_API_KEY" and not ok:
            missing.append(k)
        elif not ok and k != "OPENROUTER_API_KEY":
            missing.append(k)
        print(f"  {'OK' if ok else 'MISSING'}: {k}")

    print("\n=== RECOMMENDED AGENT ===")
    for k in RECOMMENDED_AGENT:
        v = (agent.get(k) or "").strip()
        # Cursor key optional
        label = "OK" if v else ("OPTIONAL_EMPTY" if k.startswith("CURSOR") else "EMPTY")
        print(f"  {label}: {k}")

    print("\n=== WEB CHECKS ===")
    api = (web.get("NEXT_PUBLIC_API_URL") or "").strip()
    print(f"  NEXT_PUBLIC_API_URL={redact('NEXT_PUBLIC_API_URL', api)}")
    if CURRENT_AGENT_HOST in api:
        print("  OK: points at current Agent domain")
    elif "4356" in api or "ca7c" in api:
        print("  BAD: stale Agent domain")
        missing.append("NEXT_PUBLIC_API_URL_STALE")
    else:
        print("  WARN: unexpected API host")

    print("\n=== SANITY ===")
    db = agent.get("DATABASE_URL") or ""
    print("  db_railway_internal=", "railway.internal" in db)
    print("  teacher_upstream=", agent.get("TEACHER_UPSTREAM"))
    print("  prefer_internal=", agent.get("PREFER_INTERNAL"))
    print("  app_env=", agent.get("APP_ENV"))
    print("  cloud_workspaces=", agent.get("CLOUD_WORKSPACES"))
    print("  force_simulate=", agent.get("MODEL_GATEWAY_FORCE_SIMULATE"))
    print("  openrouter_set=", bool((agent.get("OPENROUTER_API_KEY") or "").strip()))
    print("  cursor_set=", bool((agent.get("CURSOR_API_KEY") or "").strip()))

    issues = []
    if (agent.get("TEACHER_UPSTREAM") or "").strip().lower() == "cursor" and not (
        agent.get("CURSOR_API_KEY") or ""
    ).strip():
        issues.append("TEACHER_UPSTREAM=cursor without CURSOR_API_KEY")
    if (agent.get("PREFER_INTERNAL") or "").strip().lower() in {"1", "true", "yes"}:
        issues.append("PREFER_INTERNAL=true on cloud (no Ollama) — should be false")
    if (agent.get("MODEL_GATEWAY_FORCE_SIMULATE") or "").strip().lower() in {
        "1",
        "true",
        "yes",
    }:
        issues.append("MODEL_GATEWAY_FORCE_SIMULATE=true blocks real teachers")
    if (agent.get("CLOUD_WORKSPACES") or "").strip().lower() not in {"1", "true", "yes"}:
        issues.append("CLOUD_WORKSPACES not true — blank projects may use ephemeral paths")
    if CURRENT_AGENT_HOST not in api:
        issues.append("web NEXT_PUBLIC_API_URL not on current Agent host")

    print("\n=== ISSUES ===")
    if not issues and not missing:
        print("  none — ready")
        return 0
    for m in missing:
        print("  missing:", m)
    for i in issues:
        print("  issue:", i)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
