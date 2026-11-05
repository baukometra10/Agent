from __future__ import annotations

from pathlib import Path

from app.deployment.adapters.base import DeployRequest, DeployResult


class DockerLocalAdapter:
    name = "docker_local"
    description = "Build/tag local Docker image when Dockerfile exists; never push unless enabled."

    async def deploy(self, request: DeployRequest) -> DeployResult:
        root = Path(request.workspace_path)
        repo = root / "repo"
        base = repo if repo.exists() else root
        dockerfile = base / "Dockerfile"
        if not dockerfile.exists():
            return DeployResult(
                provider=self.name,
                status="skipped_no_dockerfile",
                simulated=True,
                message="No Dockerfile in workspace — recorded plan only.",
                artifact={"path": str(base)},
            )

        tag = f"evolve/{request.project_slug}:{request.target}"
        if request.force_simulate:
            return DeployResult(
                provider=self.name,
                status="simulated_docker_build",
                simulated=True,
                message=f"Would run: docker build -t {tag} {base}",
                artifact={"tag": tag, "dockerfile": str(dockerfile)},
            )

        # Real local build — still no registry push
        import asyncio

        proc = await asyncio.create_subprocess_exec(
            "docker",
            "build",
            "-t",
            tag,
            str(base),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await proc.communicate()
        ok = proc.returncode == 0
        return DeployResult(
            provider=self.name,
            status="docker_build_ok" if ok else "docker_build_failed",
            simulated=False,
            message=(out or err or b"").decode("utf-8", errors="ignore")[:1500],
            artifact={"tag": tag, "returncode": proc.returncode},
        )
