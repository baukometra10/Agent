import pytest

from app.deployment.adapters.base import DeployRequest
from app.deployment.adapters.docker_local import DockerLocalAdapter
from app.deployment.adapters.registry import get_deploy_adapter, list_deploy_adapters
from app.deployment.adapters.simulate import SimulateAdapter


@pytest.mark.asyncio
async def test_simulate_adapter():
    result = await SimulateAdapter().deploy(
        DeployRequest(
            project_name="Demo",
            project_slug="demo",
            workspace_path=".",
            target="staging",
        )
    )
    assert result.simulated is True
    assert result.status == "simulated_success"


@pytest.mark.asyncio
async def test_docker_local_without_dockerfile(tmp_path):
    result = await DockerLocalAdapter().deploy(
        DeployRequest(
            project_name="Demo",
            project_slug="demo",
            workspace_path=str(tmp_path),
            target="staging",
            force_simulate=True,
        )
    )
    assert result.status == "skipped_no_dockerfile"


def test_registry_lists_providers():
    names = {a["name"] for a in list_deploy_adapters()}
    assert {"simulate", "docker_local", "azure_container_apps"} <= names
    assert get_deploy_adapter("azure_container_apps").name == "azure_container_apps"
    assert get_deploy_adapter("unknown").name == "simulate"
