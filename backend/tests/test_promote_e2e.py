import json
from pathlib import Path

from app.autopilot.promote import promote_sandbox_experiment


def test_promote_sandbox_to_project(tmp_path: Path):
    workspace = tmp_path / "project"
    repo = workspace / "repo"
    repo.mkdir(parents=True)
    sandbox = tmp_path / "run" / "sandbox"
    sandbox.mkdir(parents=True)
    (sandbox / ".evolve-sandbox").write_text("ok", encoding="utf-8")
    exp = sandbox / "evolve-sandbox"
    exp.mkdir()
    target_rel = "evolve-sandbox/fix.txt"
    (exp / "fix.txt").write_text("owned fix", encoding="utf-8")
    (exp / "manifest.json").write_text(
        json.dumps({"files": [{"path": target_rel}]}),
        encoding="utf-8",
    )
    evidence = {"sandbox_path": str(exp / "manifest.json")}
    result = promote_sandbox_experiment(project_workspace=workspace, evidence=evidence)
    assert result["ok"] is True
    assert result["originals_touched"] is True
    promoted = repo / "evolve-sandbox" / "fix.txt"
    assert promoted.exists()
    assert promoted.read_text(encoding="utf-8") == "owned fix"
