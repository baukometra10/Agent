"""Model Ownership Registry — provenance for base, data, adapters, eval, approver."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.config import Settings, get_settings
from app.intelligence.ecosystem import SPIXA_FAMILY


class ModelOwnershipRegistry:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.root = Path(self.settings.learning_data_root) / "ownership_registry"
        self.root.mkdir(parents=True, exist_ok=True)
        self.index_path = self.root / "index.json"

    def _load_index(self) -> dict[str, Any]:
        if not self.index_path.exists():
            return {"specialties": {}, "updated_at": None}
        try:
            return json.loads(self.index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"specialties": {}, "updated_at": None}

    def _save_index(self, data: dict[str, Any]) -> None:
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.index_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _version_path(self, specialty: str, version_id: str) -> Path:
        d = self.root / specialty
        d.mkdir(parents=True, exist_ok=True)
        return d / f"{version_id}.json"

    def ensure_skeleton(self) -> dict[str, Any]:
        idx = self._load_index()
        specs = idx.setdefault("specialties", {})
        for fam in SPIXA_FAMILY:
            sp = fam["specialty"]
            if sp not in specs:
                specs[sp] = {
                    "product": fam["product"],
                    "base_model": {
                        "id": self.settings.internal_model_name or "unset",
                        "license": "document_before_commercial_use",
                        "source": self.settings.internal_model_base_url or "local",
                    },
                    "latest_version_id": None,
                    "versions": [],
                }
        self._save_index(idx)
        return idx

    def register_release(
        self,
        *,
        specialty: str,
        adapter: str,
        training: dict[str, Any] | None = None,
        dataset_sources: list[dict[str, Any]] | None = None,
        eval_results: dict[str, Any] | None = None,
        approver: str = "",
        release_id: str = "",
        weights_path: str = "",
        notes: str = "",
    ) -> dict[str, Any]:
        idx = self.ensure_skeleton()
        version_id = str(uuid4())
        product = next((f["product"] for f in SPIXA_FAMILY if f["specialty"] == specialty), specialty)
        record = {
            "version_id": version_id,
            "specialty": specialty,
            "product": product,
            "release_id": release_id or version_id,
            "base_model": {
                "id": self.settings.internal_model_name or "unset",
                "host": self.settings.internal_model_base_url or "",
                "license": "document_before_commercial_use",
                "note": "Adapter ownership ≠ automatic ownership of base weights",
            },
            "adapter": {
                "name": adapter,
                "weights_path": weights_path,
            },
            "training": training or {},
            "dataset_sources": dataset_sources
            or [
                {
                    "kind": "distillation_corpus",
                    "path": str(Path(self.settings.distillation_data_root) / specialty / "train.jsonl"),
                    "rights": "verify_per_source",
                }
            ],
            "evaluation": eval_results or {},
            "approver": approver,
            "approved_at": datetime.now(timezone.utc).isoformat() if approver else None,
            "notes": notes,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        path = self._version_path(specialty, version_id)
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        entry = idx["specialties"].setdefault(
            specialty, {"product": product, "versions": [], "latest_version_id": None}
        )
        entry["product"] = product
        entry["versions"] = list(entry.get("versions") or []) + [version_id]
        entry["latest_version_id"] = version_id
        entry["base_model"] = record["base_model"]
        self._save_index(idx)
        record["path"] = str(path)
        return record

    def list_specialty(self, specialty: str) -> dict[str, Any]:
        idx = self.ensure_skeleton()
        meta = (idx.get("specialties") or {}).get(specialty) or {}
        versions = []
        for vid in meta.get("versions") or []:
            path = self._version_path(specialty, str(vid))
            if path.exists():
                versions.append(json.loads(path.read_text(encoding="utf-8")))
        return {"specialty": specialty, "meta": meta, "versions": versions}

    def catalog(self) -> dict[str, Any]:
        idx = self.ensure_skeleton()
        return {
            "name": "Model Ownership Registry",
            "name_ar": "سجل ملكية النماذج",
            "index": idx,
            "fields": [
                "base_model_source_license",
                "training_data_sources_rights",
                "weight_adapter_versions",
                "training_config",
                "evaluation_results",
                "approver_identity",
            ],
        }


_registry: ModelOwnershipRegistry | None = None


def get_ownership_registry() -> ModelOwnershipRegistry:
    global _registry
    if _registry is None:
        _registry = ModelOwnershipRegistry()
    return _registry
