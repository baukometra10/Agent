from __future__ import annotations

from typing import Any

from app.deployment.adapters.azure_container_apps import AzureContainerAppsAdapter
from app.deployment.adapters.docker_local import DockerLocalAdapter
from app.deployment.adapters.simulate import SimulateAdapter

_ADAPTERS = {
    SimulateAdapter.name: SimulateAdapter(),
    DockerLocalAdapter.name: DockerLocalAdapter(),
    AzureContainerAppsAdapter.name: AzureContainerAppsAdapter(),
}


def get_deploy_adapter(name: str | None = None):
    key = (name or "simulate").strip().lower() or "simulate"
    if key not in _ADAPTERS:
        return _ADAPTERS["simulate"]
    return _ADAPTERS[key]


def list_deploy_adapters() -> list[dict[str, Any]]:
    return [
        {"name": a.name, "description": a.description}
        for a in _ADAPTERS.values()
    ]
