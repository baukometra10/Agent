from app.agents.hierarchy import classify_intent
from app.agents.master import MasterConductor


def test_classify_implement_intent_arabic():
    route = classify_intent("ابني تطبيق FastAPI للصحة")
    assert route.intent == "implement"
    assert route.draft_proposal is True
    assert "FullstackDeveloper" in route.specialists


def test_classify_security_intent():
    route = classify_intent("audit security and permissions")
    assert route.intent == "security"
    assert route.include_critic is True


def test_classify_design_intent():
    route = classify_intent("حسّن تصميم الواجهة و UX")
    assert route.intent == "design"


def test_ide_coding_turn_detected_from_scaffold():
    msg = (
        "You are Spixa — the chief IDE coding agent.\n"
        "Mode=agent: understand → brief plan → implement with file blocks immediately.\n"
        "=== USER MESSAGE (reply in this language) ===\n"
        "bau mir eine app"
    )
    assert MasterConductor._is_ide_coding_turn(msg) is True
    assert MasterConductor._is_ide_coding_turn("ابني تطبيق فقط") is False
    assert MasterConductor._extract_mode("[mode:agent]\nbau mir eine app") == "agent"


def test_handoff_restores_coding_when_not_ready(tmp_path, monkeypatch):
    from app.config import Settings
    from app.ownership.handoff import OwnershipHandoff

    settings = Settings(
        learning_data_root=tmp_path / "learning",
        auto_retire_ready_teachers=True,
    )
    h = OwnershipHandoff(settings=settings)
    h.retire_specialty("coding", reason="stale_auto_ready")
    assert "coding" in (h.list_retired().get("specialties") or [])
    # Force not handoff_ready via monkeypatch of readiness rows
    monkeypatch.setattr(
        h,
        "_readiness_rows",
        lambda: [
            {
                "specialty": "coding",
                "handoff_ready": False,
                "promoted": False,
                "examples": 10,
                "min_examples": 3,
                "enough_data": True,
                "internal_id": "internal/coding",
                "host": "openai_compatible",
            }
        ],
    )
    out = h.sync_auto_retire()
    assert out and "coding" in (out.get("auto_restored") or [])
    assert "coding" not in (h.list_retired().get("specialties") or [])


def test_master_evaluates_specialists():
    evals = MasterConductor._evaluate_specialists(
        [
            {
                "agent": "FullstackDeveloper",
                "summary": (
                    "Implement FastAPI routes and a small frontend. "
                    "Create file path api/main.py plus pages for login and alerts dashboard."
                ),
            },
            {
                "agent": "WeakAgent",
                "summary": "unclear, need more info",
                "simulated": True,
            },
        ],
        critic={"summary": "WeakAgent has risk of wrong approach"},
        user_message="ابني تطبيق",
    )
    assert len(evals) == 2
    by = {e["agent"]: e for e in evals}
    assert by["FullstackDeveloper"]["score"] >= 0.6
    assert by["WeakAgent"]["score"] < 0.6
    assert "needs" in by["WeakAgent"]
