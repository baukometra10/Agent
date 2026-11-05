from pathlib import Path

from app.config import Settings
from app.factory.gates import better_than_teacher, eval_passes_gates, regression_vs_baseline
from app.factory.orchestrator import ModelFactory
from app.factory.synthetic import SyntheticDataFactory


def test_blueprint_has_five_engines(tmp_path: Path):
    settings = Settings(
        learning_data_root=tmp_path / "learning",
        distillation_data_root=tmp_path / "distill",
        training_artifacts_root=tmp_path / "train",
        eval_data_root=tmp_path / "eval",
    )
    factory = ModelFactory(settings=settings)
    bp = factory.blueprint()
    assert len(bp["engines"]) == 5
    assert bp["hard_rule"]["require_human_approval"] is True
    assert bp["hard_rule"]["auto_mutate_production_weights"] is False
    assert "human_approve" in bp["knowledge_flow"]


def test_gates_require_promote_flag():
    ok, reasons = eval_passes_gates({"promote": False, "gates": {}})
    assert ok is False
    assert "eval_promote_false" in reasons

    report = {
        "promote": True,
        "student_score": 0.9,
        "teacher_score": 0.8,
        "gates": {"parity_vs_teacher": True, "min_absolute": True, "not_stub": True},
    }
    ok, _ = eval_passes_gates(report)
    assert ok is True
    verdict = better_than_teacher(report)
    assert verdict["needs_human_approval"] is True
    assert verdict["beat_or_parity"] is True

    reg_ok, reg_reasons = regression_vs_baseline(report, 0.95, tolerance=0.02)
    assert reg_ok is False
    assert reg_reasons
    blocked = better_than_teacher(report, baseline_student_score=0.95, regression_tolerance=0.02)
    assert blocked["gates_ok"] is False
    assert blocked["regression_ok"] is False


def test_approve_reject_release(tmp_path: Path):
    settings = Settings(
        learning_data_root=tmp_path / "learning",
        distillation_data_root=tmp_path / "distill",
        training_artifacts_root=tmp_path / "train",
        eval_data_root=tmp_path / "eval",
    )
    factory = ModelFactory(settings=settings)
    release = {
        "id": "rel-test-1",
        "specialty": "coding",
        "status": "pending_approval",
        "eval": {"student_score": 0.9, "teacher_score": 0.8},
    }
    factory._write_release(release)

    bad = factory.approve_release("missing")
    assert bad["ok"] is False

    # Maturity gates block ship unless force (staging) or evidence present
    blocked = factory.approve_release("rel-test-1", approver="tester")
    assert blocked["ok"] is False
    assert blocked["error"] == "maturity_gates_failed"

    approved = factory.approve_release("rel-test-1", approver="tester", force=True)
    assert approved["ok"] is True
    assert approved["release"]["status"] == "approved"
    assert approved["production"] is True
    assert approved.get("ownership_registry")

    # second approve should fail
    again = factory.approve_release("rel-test-1", force=True)
    assert again["ok"] is False

    release2 = {
        "id": "rel-test-2",
        "specialty": "reasoning",
        "status": "pending_approval",
    }
    factory._write_release(release2)
    rejected = factory.reject_release("rel-test-2", reason="parity weak")
    assert rejected["ok"] is True
    assert rejected["release"]["status"] == "rejected"


def test_synthetic_factory_writes_batch(tmp_path: Path):
    settings = Settings(
        learning_data_root=tmp_path / "learning",
        distillation_data_root=tmp_path / "distill",
        distillation_enabled=True,
    )
    specialty_dir = settings.distillation_data_root / "coding"
    specialty_dir.mkdir(parents=True)
    (specialty_dir / "train.jsonl").write_text(
        '{"id":"s1","messages":[{"role":"user","content":"write add"},'
        '{"role":"assistant","content":"def add(a,b): return a+b"}]}\n',
        encoding="utf-8",
    )
    out = SyntheticDataFactory(settings=settings).generate(
        specialty="coding", max_variants=2, promote_verified=True
    )
    assert out["ok"] is True
    assert out["variants"] >= 1
    assert Path(out["path"]).exists()
