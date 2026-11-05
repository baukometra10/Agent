from __future__ import annotations

from app.config import get_settings
from app.deployment.adapters.base import DeployRequest, DeployResult


class AzureContainerAppsAdapter:
    name = "azure_container_apps"
    description = "Azure Container Apps deploy intent; live az calls only when AZURE_DEPLOY_ENABLED=true."

    async def deploy(self, request: DeployRequest) -> DeployResult:
        settings = get_settings()
        resource_group = settings.azure_resource_group or "(unset)"
        app_name = settings.azure_container_app_name or request.project_slug
        planned = {
            "resource_group": resource_group,
            "app": app_name,
            "target": request.target,
            "command": (
                f"az containerapp update -n {app_name} -g {resource_group} "
                f"--image evolve/{request.project_slug}:{request.target}"
            ),
        }

        if request.force_simulate or not settings.azure_deploy_enabled:
            return DeployResult(
                provider=self.name,
                status="simulated_azure_plan",
                simulated=True,
                message=(
                    "Azure deploy planned (simulate). Set AZURE_DEPLOY_ENABLED=true and "
                    "force_simulate=false after human gate to attempt live az CLI."
                ),
                artifact=planned,
            )

        import asyncio

        # Minimal live path — requires az logged in; still human-gated by caller
        cmd = [
            "az",
            "containerapp",
            "show",
            "-n",
            app_name,
            "-g",
            resource_group,
            "-o",
            "json",
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await proc.communicate()
        ok = proc.returncode == 0
        return DeployResult(
            provider=self.name,
            status="azure_app_reachable" if ok else "azure_app_missing_or_auth",
            simulated=False,
            message=(out or err or b"").decode("utf-8", errors="ignore")[:1500],
            artifact={**planned, "returncode": proc.returncode},
        )
