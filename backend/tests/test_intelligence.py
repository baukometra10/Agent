from pathlib import Path

from app.intelligence.code_intelligence import analyze_codebase
from app.intelligence.engine import run_project_intelligence


def test_code_intelligence_extracts_fastapi_routes(tmp_path: Path):
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    (app_dir / "main.py").write_text(
        """
from fastapi import FastAPI
app = FastAPI()

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/items")
async def create_item():
    return {"id": 1}

class Service:
    def run(self):
        return 1
""",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text(
        "# Demo API\n\nThis service manages items for operators and admins.\n",
        encoding="utf-8",
    )

    code = analyze_codebase(tmp_path)
    methods = {(e.method, e.path) for e in code.api_endpoints}
    assert ("GET", "/health") in methods
    assert ("POST", "/items") in methods
    assert any(s.kind == "class" and s.name == "Service" for s in code.symbols)

    report = run_project_intelligence(tmp_path)
    assert report.coverage["understanding_progress"] > 0.2
    assert report.business.get("purpose")
    kinds = {item["kind"] for item in report.knowledge}
    assert "fact" in kinds
    assert any(item["category"] == "api" for item in report.knowledge)


def test_intelligence_marks_missing_purpose_as_unverified(tmp_path: Path):
    (tmp_path / "main.py").write_text("print('x')\n", encoding="utf-8")
    report = run_project_intelligence(tmp_path)
    purpose_nodes = [k for k in report.knowledge if k.get("category") == "purpose"]
    assert purpose_nodes
    assert purpose_nodes[0]["kind"] == "unverified"
