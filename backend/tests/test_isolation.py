from pathlib import Path

import pytest

from app.config import Settings
from app.security.isolation import ensure_project_isolation, make_namespace
from app.security.sandbox import plan_sandbox_run


def test_namespaces_are_project_specific(tmp_path: Path):
    settings = Settings(workspaces_root=tmp_path)
    a = ensure_project_isolation(name="Acme ERP", settings=settings, slug="acme-erp")
    b = ensure_project_isolation(name="Shop", settings=settings, slug="shop")
    assert a.namespace != b.namespace
    assert a.workspace_path != b.workspace_path
    assert a.workspace_path.exists()
    assert make_namespace("acme-erp").startswith("evolve-acme-erp-")


def test_sandbox_blocked_by_default(tmp_path: Path):
    settings = Settings(workspaces_root=tmp_path, allow_untrusted_code_execution=False)
    isolation = ensure_project_isolation(name="Unsafe", settings=settings, slug="unsafe")
    result = plan_sandbox_run(isolation, settings, command=["pytest"])
    assert result.allowed is False
