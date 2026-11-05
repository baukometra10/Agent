# Spixa golden IDE smoke — requires API (.\start.ps1) unless -PytestOnly.
param(
  [switch]$Fast,
  [switch]$Venture,
  [switch]$PytestOnly,
  [string]$Api = "http://127.0.0.1:7000"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
if (-not $Root) { $Root = (Get-Location).Path }
Set-Location $Root

$Py = $null
foreach ($cand in @(
  "$Root\backend\.venv\Scripts\python.exe",
  "$Root\.venv\Scripts\python.exe",
  "python"
)) {
  if ($cand -eq "python") { $Py = "python"; break }
  if (Test-Path $cand) { $Py = $cand; break }
}

$env:PYTHONUNBUFFERED = "1"
Write-Host "==> Golden smoke (API=$Api)" -ForegroundColor Cyan
Write-Host "    DB tip: .\start.ps1 uses SQLite without Docker; Postgres when Docker Desktop is up." -ForegroundColor DarkGray

if (-not $PytestOnly) {
  try {
    $null = Invoke-WebRequest -Uri "$Api/health" -UseBasicParsing -TimeoutSec 3
  } catch {
    Write-Host "API not reachable at $Api — start with .\start.ps1 first, or use -PytestOnly." -ForegroundColor Yellow
    exit 2
  }
  $env:SPIXA_API = $Api
  $smokeArgs = @("-u", "$Root\scripts\ide-golden-smoke.py")
  if ($Fast) { $smokeArgs += "--fast" }
  if ($Venture) { $smokeArgs += "--venture" }
  & $Py @smokeArgs
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

Write-Host "==> Pytest IDE golden path (in-process SQLite)" -ForegroundColor Cyan
Push-Location "$Root\backend"
try {
  & $Py -m pytest tests/test_ide_golden_path.py -q --tb=short
  exit $LASTEXITCODE
} finally {
  Pop-Location
}
