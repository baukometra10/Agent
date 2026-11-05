from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.autopilot.engine import AutopilotEngine, reset_autopilot
from app.config import Settings, get_settings
from app.db.base import Base
from app.learning.experience import ExperienceJournal, reset_experience_journal
from app.services.project_service import ProjectService


def test_experience_learns_from_success_and_failure(tmp_path: Path):
    reset_experience_journal()
    settings = Settings(
        learn_from_everything=True,
        fast_handoff_enabled=True,
        distillation_enabled=True,
        distillation_data_root=tmp_path / "distill",
        learning_data_root=tmp_path / "learning",
    )
    journal = ExperienceJournal(settings=settings)
    ok = journal.record_success(
        title="Good patch",
        detail="Added health endpoint with tests.",
        specialty="coding",
    )
    bad = journal.record_failure(
        title="Broken import",
        detail="ModuleNotFoundError: missing package",
        specialty="coding",
    )
    assert ok["recorded"] and bad["recorded"]
    assert ok["distill"]["accepted"] is True
    assert bad["distill"]["accepted"] is True
    stats = journal.stats()
    assert stats["counts"].get("success", 0) >= 1
    assert stats["counts"].get("failure", 0) >= 1
    reset_experience_journal()


@pytest.mark.asyncio
async def test_autopilot_clones_sandbox_never_touches_original(tmp_path: Path, monkeypatch):
    sample = tmp_path / "src"
    sample.mkdir()
    (sample / "main.py").write_text("print('safe')\n", encoding="utf-8")
    workspaces = tmp_path / "workspaces"
    monkeypatch.setenv("WORKSPACES_ROOT", str(workspaces))
    get_settings.cache_clear()
    reset_autopilot()
    reset_experience_journal()

    settings = Settings(
        workspaces_root=workspaces,
        learning_data_root=tmp_path / "learning",
        distillation_data_root=tmp_path / "distill",
        learn_from_everything=True,
        fast_handoff_enabled=True,
        distillation_enabled=True,
        autopilot_max_projects=5,
    )
    # Point autopilot root under tmp
    engine_api = AutopilotEngine(settings=settings)
    engine_api.root = tmp_path / "autopilot"
    engine_api.state_path = engine_api.root / "state.json"

    db_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as session:
        project = await ProjectService(session, settings=settings).create_from_path(
            name="AutoPilot Demo",
            local_path=str(sample),
            slug="autopilot-demo",
            owner_email="owner@example.com",
        )
        original = Path(project.workspace_path) / "main.py"
        if not original.exists():
            # intake may place under repo/
            repo_main = Path(project.workspace_path) / "repo" / "main.py"
            original = repo_main if repo_main.exists() else original
        before = original.read_text(encoding="utf-8") if original.exists() else ""

        engine_api.enable(notify_email="owner@example.com")
        result = await engine_api.run_once(session, force=True, notify_email="owner@example.com")
        assert result["ok"] is True
        assert result["report"]["originals_touched"] is False
        for block in result["report"]["projects"]:
            assert block.get("originals_touched") is False
            sandbox = Path(block["sandbox_path"])
            assert sandbox.exists()
            assert ".evolve-sandbox" in [p.name for p in sandbox.iterdir()]
            assert sandbox.resolve() != Path(project.workspace_path).resolve()

        after = original.read_text(encoding="utf-8") if original.exists() else ""
        assert before == after  # original never mutated

        # Manual chat pauses autonomous cycles
        paused = engine_api.pause_for_manual(reason="user_chat")
        assert paused["paused_for_manual"] is True
        assert paused["ui_mode"] == "paused_manual"
        resumed = engine_api.resume_autonomous()
        assert resumed["paused_for_manual"] is False
        assert resumed["ui_mode"] == "autonomous"

    await db_engine.dispose()
    get_settings.cache_clear()
    reset_autopilot()
    reset_experience_journal()


def test_loop_status_reports_interval(tmp_path: Path, monkeypatch):
    from app.autopilot.loop import loop_status

    monkeypatch.setenv("AUTOPILOT_INTERVAL_SECONDS", "90")
    get_settings.cache_clear()
    reset_autopilot()
    st = loop_status()
    assert st["interval_seconds"] >= 30
    assert "loop_running" in st
    get_settings.cache_clear()
    reset_autopilot()


def test_sandbox_review_flags_missing_tests(tmp_path: Path):
    from app.autopilot.sandbox_review import review_sandbox

    sandbox = tmp_path / "sb"
    sandbox.mkdir()
    (sandbox / "app.py").write_text("print('hi')\n# TODO harden\n", encoding="utf-8")
    review = review_sandbox(sandbox)
    assert review["files_scanned"] >= 1
    titles = " ".join(i["title"] for i in review["improvements"])
    assert "اختبارات" in titles or "TODO" in titles


def test_sandbox_patch_writes_only_inside_marked_sandbox(tmp_path: Path):
    from app.autopilot.sandbox_patch import apply_experimental_patches
    from app.autopilot.sandbox_review import review_sandbox

    sandbox = tmp_path / "sb"
    sandbox.mkdir()
    (sandbox / ".evolve-sandbox").write_text("{}", encoding="utf-8")
    (sandbox / "app.py").write_text("print(1)\n", encoding="utf-8")
    review = review_sandbox(sandbox)
    result = apply_experimental_patches(
        sandbox, project_name="Demo", review=review, advisory={"message_ar": "تجربة"}
    )
    assert result["ok"] is True
    assert result["originals_touched"] is False
    assert (sandbox / "evolve-sandbox" / "SUGGESTIONS.md").exists()
    assert (sandbox / "evolve-sandbox" / "experiment.diff").exists()
    # Refuse unmarked path
    bad = tmp_path / "not-sandbox"
    bad.mkdir()
    try:
        apply_experimental_patches(bad, project_name="X", review=review)
        assert False, "expected PermissionError"
    except PermissionError:
        pass
