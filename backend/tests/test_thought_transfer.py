from pathlib import Path

from app.config import Settings
from app.distillation.engine import DistillationEngine
from app.distillation.thought_transfer import seed_thought_transfer


def test_thought_transfer_seeds_many(tmp_path: Path):
    settings = Settings(
        distillation_data_root=tmp_path / "d",
        learning_data_root=tmp_path / "l",
        distillation_enabled=True,
    )
    engine = DistillationEngine(settings=settings)
    out = seed_thought_transfer(settings=settings, engine=engine, also_journal=False)
    assert out["ok"] is True
    assert out["accepted"] >= 50
    assert out["by_specialty"].get("coding", 0) >= 5
    assert out["by_specialty"].get("reasoning", 0) >= 5
    coding = settings.distillation_data_root / "coding" / "train.jsonl"
    assert coding.exists()
    assert coding.stat().st_size > 1000
