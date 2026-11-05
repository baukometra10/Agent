# Spixa → Railway (isolated monorepo: backend + frontend + Postgres)
# Prerequisites: railway login (done), Dockerfiles in backend/ and frontend/
#
# Usage:
#   .\scripts\deploy-railway.ps1           # create project + print next steps
#   .\scripts\deploy-railway.ps1 -DeployApi
#   .\scripts\deploy-railway.ps1 -DeployWeb

param(
  [switch]$DeployApi,
  [switch]$DeployWeb,
  [string]$ProjectName = "spixa"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot

Write-Host @"

Why Docker showed nothing in Railway UI
---------------------------------------
1) This folder had NO git repo / no GitHub link — Railway GitHub+Docker needs a connected repo.
2) Dockerfile is NOT at repo root — it lives in backend/ and frontend/.
3) This app is THREE services: Postgres + API + Web (not one Docker image).

Recommended setup (isolated monorepo)
-------------------------------------
In Railway dashboard → New Project:

  A) Add Plugin: PostgreSQL

  B) New Service → Empty Service → name it "api"
     Settings → Root Directory: /backend
     Settings → Builder: Dockerfile
     Variables:
       DATABASE_URL=\${{Postgres.DATABASE_URL}}   # then edit scheme to postgresql+asyncpg://
       DATABASE_URL_SYNC=\${{Postgres.DATABASE_URL}}
       SECRET_KEY=<long-random>
       WORKSPACES_ROOT=/data/workspaces
       OPENROUTER_API_KEY=<your-key>
       TEACHER_UPSTREAM=openrouter
       FAST_HANDOFF_ENABLED=true
       LEARN_FROM_EVERYTHING=true
       DISTILLATION_ENABLED=true
       PREFER_INTERNAL=false
     Networking → Generate Domain

  C) New Service → Empty Service → name it "web"
     Settings → Root Directory: /frontend
     Settings → Builder: Dockerfile
     Variables:
       NEXT_PUBLIC_API_URL=https://<api-public-domain>
     Networking → Generate Domain

Connect source: GitHub repo OR run 'railway up' from each folder after 'railway link'.

"@

if (-not (Test-Path "$Root\.git")) {
  Write-Host "NOTE: No .git yet. For GitHub deploy: git init && push to GitHub, then connect the repo in Railway." -ForegroundColor Yellow
}

if ($DeployApi) {
  Set-Location "$Root\backend"
  railway up --detach
}

if ($DeployWeb) {
  Set-Location "$Root\frontend"
  railway up --detach
}
