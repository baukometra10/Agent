"""Path-3 local proof: IDE apply feeds coding maturity; independence includes workspace apply."""

from __future__ import annotations

import tempfile

import pytest

from app.maturity.scorecard import SpecialtyMaturity
from app.ownership.independence import IndependenceMode
from app.workspace.edits import apply_edits_to_workspace


def test_apply_edits_records_coding_maturity(tmp_path, monkeypatch):
    data = tmp_path / "learning"
    data.mkdir()
    monkeypatch.setenv("LEARNING_DATA_ROOT", str(data))
    from app.config import get_settings

    get_settings.cache_clear()

    ws = tmp_path / "ws"
    ws.mkdir()
    result = apply_edits_to_workspace(
        str(ws),
        [{"path": "a.py", "content": "print(1)\n"}],
        maturity_source="unit_test",
    )
    assert result["ok"] is True
    assert "a.py" in result["applied"]

    board = SpecialtyMaturity()
    tasks = [r for r in board._read_jsonl(board.task_path) if r.get("source") == "unit_test"]
    assert tasks and tasks[-1]["specialty"] == "coding" and tasks[-1]["success"] is True
    get_settings.cache_clear()


def test_apply_edits_can_skip_maturity(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    result = apply_edits_to_workspace(
        str(ws),
        [{"path": "b.py", "content": "x=1\n"}],
        record_maturity=False,
    )
    assert result["ok"] is True


@pytest.mark.asyncio
async def test_independence_includes_ide_workspace_apply(monkeypatch, tmp_path):
    monkeypatch.setenv("LEARNING_DATA_ROOT", str(tmp_path / "learning"))
    from app.config import get_settings

    get_settings.cache_clear()
    report = await IndependenceMode().run_probe()
    ids = {c["id"] for c in report.get("checks") or []}
    assert "ide_workspace_apply" in ids
    hit = next(c for c in report["checks"] if c["id"] == "ide_workspace_apply")
    assert hit.get("ok") is True
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_maturity_api_task_outcome(client):
    res = await client.post(
        "/system/intelligence/maturity/task-outcome",
        json={"specialty": "coding", "success": True, "source": "pytest"},
    )
    assert res.status_code == 200, res.text
    board = await client.get("/system/intelligence/maturity/coding")
    assert board.status_code == 200, board.text
    card = board.json()
    assert card.get("specialty") == "coding"
