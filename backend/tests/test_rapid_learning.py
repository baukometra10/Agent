from pathlib import Path

from app.config import Settings
from app.learning.rapid_system import RapidLearningSystem


def test_blueprint_has_seven_layers(tmp_path: Path):
    settings = Settings(
        learning_data_root=tmp_path / "learning",
        distillation_data_root=tmp_path / "distill",
    )
    sys = RapidLearningSystem(settings=settings)
    bp = sys.blueprint()
    assert len(bp["layers"]) == 7
    assert bp["doctrine"] == "Internal Intelligence First"
    assert len(bp["multi_teacher"]["roster"]) == 4
    assert len(bp["competitive_lab"]["domains"]) >= 7
    assert bp["multi_agent_learning_lab"]["learns_from"]


def test_execution_verified_promotes_success(tmp_path: Path):
    settings = Settings(
        learning_data_root=tmp_path / "learning",
        distillation_data_root=tmp_path / "distill",
    )
    sys = RapidLearningSystem(settings=settings)
    out = sys.record_execution_verified(
        patch_summary="fix add() edge case",
        tests_ok=True,
        sandbox_ok=True,
        repair_notes="def add(a,b): return a+b",
        promote=True,
    )
    assert out["ok"] is True
    assert out["distill"] is not None


def test_multi_agent_lab_session(tmp_path: Path):
    settings = Settings(
        learning_data_root=tmp_path / "learning",
        distillation_data_root=tmp_path / "distill",
    )
    sys = RapidLearningSystem(settings=settings)
    out = sys.run_multi_agent_lab(
        task="review_patch",
        artifacts={
            "reviewer": "off_by_one",
            "reviewer_severity": "verified_fix",
            "tests_ok": True,
        },
    )
    assert out["ok"] is True
    assert out["session"]["findings"]
