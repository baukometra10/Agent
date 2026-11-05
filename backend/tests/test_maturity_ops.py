import pytest

from app.config import Settings
from app.maturity.scorecard import SpecialtyMaturity
from app.ownership.independence import IndependenceMode
from app.ownership.registry import ModelOwnershipRegistry
from app.intelligence.evolution import evolution_dashboard


def test_maturity_not_based_on_adapter_counts(tmp_path):
    settings = Settings(
        learning_data_root=tmp_path / "learning",
        distillation_data_root=tmp_path / "distill",
        eval_data_root=tmp_path / "eval",
        training_artifacts_root=tmp_path / "train",
        allow_untrusted_code_execution=False,
    )
    m = SpecialtyMaturity(settings=settings)
    card = m.scorecard("coding")
    assert "task_success_rate" in card["metrics"]
    assert "human_acceptance_rate" in card["metrics"]
    assert card["production_ready"] is False
    assert card["note_ar"]


def test_ownership_registry_records_approver(tmp_path):
    settings = Settings(learning_data_root=tmp_path / "learning")
    reg = ModelOwnershipRegistry(settings=settings)
    row = reg.register_release(
        specialty="coding",
        adapter="lora-coding",
        approver="alice",
        eval_results={"student_score": 0.8},
    )
    assert row["approver"] == "alice"
    assert row["base_model"]["license"]
    listed = reg.list_specialty("coding")
    assert len(listed["versions"]) == 1


@pytest.mark.asyncio
async def test_independence_probe_runs(tmp_path):
    settings = Settings(
        learning_data_root=tmp_path / "learning",
        distillation_data_root=tmp_path / "distill",
        eval_data_root=tmp_path / "eval",
        training_artifacts_root=tmp_path / "train",
        openai_api_key="should-be-cleared-in-probe-copy",
        anthropic_api_key="x",
        internal_model_base_url="",
        allow_untrusted_code_execution=False,
    )
    report = await IndependenceMode(settings=settings).run_probe()
    assert report["mode"] == "Model Independence Mode"
    assert "checks" in report
    assert report["total"] >= 6
    ids = {c["id"] for c in report["checks"]}
    assert "teacher_keys_disabled" in ids
    assert "ecosystem_blueprint" in ids


def test_evolution_dashboard_shape(tmp_path):
    settings = Settings(
        learning_data_root=tmp_path / "learning",
        eval_data_root=tmp_path / "eval",
        distillation_data_root=tmp_path / "distill",
        training_artifacts_root=tmp_path / "train",
    )
    dash = evolution_dashboard(settings=settings)
    assert dash["name"] == "Intelligence Evolution Dashboard"
    assert len(dash["specialties"]) == 6
