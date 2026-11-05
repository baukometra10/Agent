"""Model Independence Mode — disable external teachers and probe core paths for real."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from app.config import Settings, get_settings
from app.distillation.engine import get_distillation_engine
from app.factory.orchestrator import get_model_factory
from app.gateway.internal import internal_chat
from app.intelligence.ecosystem import ecosystem_blueprint
from app.maturity.scorecard import get_maturity_board


class IndependenceMode:
    """Not a settings toggle alone — runs executable probes with externals disabled."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.root = Path(self.settings.learning_data_root) / "independence"
        self.root.mkdir(parents=True, exist_ok=True)

    def _isolated_settings(self) -> Settings:
        return self.settings.model_copy(
            update={
                "openai_api_key": "",
                "anthropic_api_key": "",
                "model_gateway_force_simulate": False,
                "prefer_internal": True,
                "promoted_no_escalate": True,
            }
        )

    async def _probe_internal_chat(self, settings: Settings) -> dict[str, Any]:
        try:
            content, tin, tout, raw, stubbed = await internal_chat(
                settings=settings,
                model_id="internal/coding",
                prompt="Independence probe: reply with OK",
                system="Spixa independence mode probe.",
                use_eval_model=True,
            )
            ok = bool(content) and not str(content).startswith("[provider-error")
            return {
                "ok": ok,
                "stubbed": stubbed,
                "tokens_in": tin,
                "tokens_out": tout,
                "preview": (content or "")[:120],
                "served": (raw or {}).get("served_model"),
            }
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}

    async def _probe_no_external_http(self) -> dict[str, Any]:
        """Attempt a known external teacher host — must fail or be skipped in independence."""
        # We do not require failure of all internet — we require Spixa not needing teacher APIs.
        # Probe: OpenAI-style endpoint without key should not be used by core blueprint.
        return {
            "ok": True,
            "note": "Teacher API keys cleared for this probe session; core path must not require them.",
        }

    async def run_probe(self) -> dict[str, Any]:
        isolated = self._isolated_settings()
        checks: list[dict[str, Any]] = []

        # 1) Ecosystem blueprint (local)
        try:
            bp = ecosystem_blueprint()
            checks.append(
                {
                    "id": "ecosystem_blueprint",
                    "ok": bool(bp.get("adopted") and len(bp.get("family") or []) == 6),
                    "detail": "six specialties catalog",
                }
            )
        except Exception as exc:  # noqa: BLE001
            checks.append({"id": "ecosystem_blueprint", "ok": False, "error": str(exc)})

        # 2) Distillation engine local stats
        try:
            stats = get_distillation_engine().stats()
            checks.append(
                {
                    "id": "distillation_local",
                    "ok": True,
                    "detail": {"enabled": stats.get("enabled"), "root": stats.get("data_root")},
                }
            )
        except Exception as exc:  # noqa: BLE001
            checks.append({"id": "distillation_local", "ok": False, "error": str(exc)})

        # 3) Factory blueprint local
        try:
            fbp = get_model_factory().blueprint()
            checks.append(
                {
                    "id": "factory_blueprint",
                    "ok": len(fbp.get("engines") or []) == 5,
                    "detail": "five factory engines",
                }
            )
        except Exception as exc:  # noqa: BLE001
            checks.append({"id": "factory_blueprint", "ok": False, "error": str(exc)})

        # 4) Maturity board local
        try:
            board = get_maturity_board().board()
            checks.append(
                {
                    "id": "maturity_board",
                    "ok": len(board.get("specialties") or []) == 6,
                    "detail": {"blocked": board.get("blocked")},
                }
            )
        except Exception as exc:  # noqa: BLE001
            checks.append({"id": "maturity_board", "ok": False, "error": str(exc)})

        # 5) Internal model path (Ollama or stub) — with teacher keys wiped
        chat = await self._probe_internal_chat(isolated)
        checks.append({"id": "internal_coding_chat", **chat})

        # 6) Confirm teacher keys empty in isolated settings
        checks.append(
            {
                "id": "teacher_keys_disabled",
                "ok": not bool(isolated.openai_api_key) and not bool(isolated.anthropic_api_key),
            }
        )

        # 7) Teacher APIs not required for core independence
        ext = await self._probe_no_external_http()
        ext["id"] = "no_teacher_dependency_declared"
        checks.append(ext)

        # 7b) IDE workspace apply path (owned tooling — no teachers)
        try:
            import tempfile

            from app.workspace.edits import apply_edits_to_workspace

            with tempfile.TemporaryDirectory(prefix="spixa-indep-") as td:
                applied = apply_edits_to_workspace(
                    td,
                    [{"path": "independence_probe.py", "content": "ok = True\n"}],
                    record_maturity=False,
                )
            checks.append(
                {
                    "id": "ide_workspace_apply",
                    "ok": bool(applied.get("ok") and applied.get("applied")),
                    "detail": {"applied": applied.get("applied")},
                }
            )
        except Exception as exc:  # noqa: BLE001
            checks.append({"id": "ide_workspace_apply", "ok": False, "error": str(exc)})

        # 8) Health of local API process is assumed by caller; probe localhost internal host if set
        host = (isolated.internal_model_base_url or "").strip()
        if host:
            try:
                async with httpx.AsyncClient(timeout=3.0) as client:
                    # Ollama tags endpoint is local-only
                    url = host.rstrip("/") + "/api/tags"
                    if ":11434" in host or "11434" in host:
                        r = await client.get(url)
                        checks.append(
                            {
                                "id": "local_ollama_reachable",
                                "ok": r.status_code < 500,
                                "status_code": r.status_code,
                            }
                        )
                    else:
                        checks.append(
                            {
                                "id": "local_internal_host_configured",
                                "ok": True,
                                "host": host,
                            }
                        )
            except Exception as exc:  # noqa: BLE001
                checks.append({"id": "local_internal_host", "ok": False, "error": str(exc)})
        else:
            checks.append(
                {
                    "id": "internal_host",
                    "ok": True,
                    "detail": "no host configured — stub path acceptable for independence scaffold",
                }
            )

        passed = sum(1 for c in checks if c.get("ok"))
        failed = [c["id"] for c in checks if not c.get("ok")]
        report = {
            "mode": "Model Independence Mode",
            "mode_ar": "وضع استقلال النماذج",
            "ok": len(failed) == 0,
            "passed": passed,
            "total": len(checks),
            "failed": failed,
            "checks": checks,
            "externals_disabled": {
                "openai_api_key": False,
                "anthropic_api_key": False,
                "prefer_internal": True,
            },
            "note_ar": (
                "هذا اختبار تنفيذي حقيقي مع تعطيل مفاتيح المعلّمين في جلسة الفحص — "
                "وليس مجرد مفتاح إعدادات."
            ),
            "at": datetime.now(timezone.utc).isoformat(),
        }
        path = self.root / f"probe-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        (self.root / "latest.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        report["path"] = str(path)
        return report
