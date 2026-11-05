from __future__ import annotations

from app.deployment.adapters.base import DeployRequest, DeployResult


class SimulateAdapter:
    name = "simulate"
    description = "Always dry-run — records intent only (safe default)."

    async def deploy(self, request: DeployRequest) -> DeployResult:
        return DeployResult(
            provider=self.name,
            status="simulated_success",
            simulated=True,
            message=f"Simulated deploy of {request.project_name} → {request.target}",
            artifact={
                "target": request.target,
                "slug": request.project_slug,
                "mode": "dry_run",
            },
        )
