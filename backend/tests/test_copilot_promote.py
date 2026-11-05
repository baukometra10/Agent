from pathlib import Path

from app.autopilot.promote import promote_sandbox_experiment
from app.autopilot.sandbox_patch import apply_experimental_patches
from app.autopilot.sandbox_review import review_sandbox


def test_promote_copies_allowlisted_files_only(tmp_path: Path):
    workspace = tmp_path / "project"
    repo = workspace / "repo"
    repo.mkdir(parents=True)
    (repo / "main.py").write_text("print('orig')\n", encoding="utf-8")

    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    (sandbox / ".evolve-sandbox").write_text("{}", encoding="utf-8")
    (sandbox / "app.py").write_text("print(1)\n", encoding="utf-8")
    review = review_sandbox(sandbox)
    experiment = apply_experimental_patches(
        sandbox, project_name="Demo", review=review, advisory={"message_ar": "x"}
    )
    assert experiment["ok"]

    # Plant a denied secret file in sandbox — must not promote
    (sandbox / ".env").write_text("SECRET=1\n", encoding="utf-8")

    result = promote_sandbox_experiment(
        project_workspace=workspace,
        evidence={
            "sandbox_path": experiment["manifest_path"],
            "diff_path": experiment["diff_path"],
        },
    )
    assert result["ok"] is True
    assert result["originals_touched"] is True
    assert not (repo / ".env").exists()
    assert (repo / "evolve-sandbox" / "SUGGESTIONS.md").exists()
    assert (repo / "evolve-sandbox" / "manifest.json").exists()


def test_promote_rejects_unmarked_source(tmp_path: Path):
    workspace = tmp_path / "project"
    workspace.mkdir()
    fake = tmp_path / "fake" / "evolve-sandbox"
    fake.mkdir(parents=True)
    manifest = fake / "manifest.json"
    manifest.write_text(
        '{"files":[{"path":"evolve-sandbox/SUGGESTIONS.md"}]}', encoding="utf-8"
    )
    try:
        promote_sandbox_experiment(
            project_workspace=workspace,
            evidence={"sandbox_path": str(manifest)},
        )
        assert False, "expected PermissionError"
    except PermissionError:
        pass
