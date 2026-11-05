from pathlib import Path

from app.config import Settings
from app.distillation.coding_tutor import seed_coding_tutor
from app.distillation.engine import DistillationEngine


def test_coding_tutor_seeds(tmp_path: Path):
    settings = Settings(
        distillation_data_root=tmp_path / "d",
        learning_data_root=tmp_path / "l",
        distillation_enabled=True,
    )
    out = seed_coding_tutor(
        settings=settings, engine=DistillationEngine(settings=settings)
    )
    assert out["ok"] is True
    assert out["accepted"] >= 200
    assert out["lessons"] >= 200
    path = settings.distillation_data_root / "coding" / "train.jsonl"
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "def " in text or "function" in text or " cons" in text or "=>" in text
