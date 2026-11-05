# Ensure Spixa DB schema is up to date (SQLite or Postgres via DATABASE_URL).
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root "backend"
Push-Location $backend
try {
  $py = Join-Path $backend ".venv\Scripts\python.exe"
  if (-not (Test-Path $py)) { $py = "python" }

  Write-Host "==> Creating / migrating tables via SQLAlchemy metadata..."
  & $py (Join-Path $root "scripts\ensure-db-inline.py")
  Write-Host "==> Done. From repo root: .\start.ps1"
} finally {
  Pop-Location
}
