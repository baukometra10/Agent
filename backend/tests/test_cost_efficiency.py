from pathlib import Path

from app.config import Settings
from app.economics.cost_efficiency import CostEfficiencyLedger


def test_cost_efficiency_report_scores(tmp_path: Path):
    settings = Settings(learning_data_root=tmp_path / "learning")
    ledger = CostEfficiencyLedger(settings=settings)
    ledger.record_event(tier="internal", success=True, tokens_in=100, tokens_out=50, quality=0.9)
    ledger.record_event(tier="internal", success=True, tokens_in=80, tokens_out=40, quality=0.85)
    ledger.record_event(
        tier="teacher", success=True, tokens_in=200, tokens_out=100, quality=0.95, escalated=True
    )
    ledger.record_training_spend(estimated_usd=0.02, job="lora-test")
    report = ledger.report()
    assert report["metric"] == "AI Cost Efficiency"
    assert report["doctrine"] == "Internal Intelligence First"
    assert report["internal_task_ratio"] >= 0
    assert report["score"] >= 0
    assert "cost_per_successful_task_usd" in report
    assert report["training_update_cost_usd"] >= 0.02
