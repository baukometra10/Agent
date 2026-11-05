# Build Spixa desktop installers (Electron) and stage downloads for the website.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Desktop = Join-Path $Root "desktop"
$OutPublic = Join-Path $Root "frontend\public\downloads"
$OutStage = Join-Path $Root "desktop\dist"

Set-Location $Desktop
Write-Host "==> npm install (desktop)" -ForegroundColor Cyan
npm install

Write-Host "==> electron-builder (zip targets)" -ForegroundColor Cyan
npx electron-builder --win zip --linux zip --mac zip --publish never 2>$null
if ($LASTEXITCODE -ne 0) {
  Write-Host "Full multi-platform build unavailable — building Windows zip only..." -ForegroundColor Yellow
  npx electron-builder --win zip --publish never
}

New-Item -ItemType Directory -Force -Path $OutPublic | Out-Null
Get-ChildItem -Path $OutStage -Filter "*.zip" -ErrorAction SilentlyContinue | ForEach-Object {
  Copy-Item $_.FullName (Join-Path $OutPublic $_.Name) -Force
  Write-Host "Staged $($_.Name) -> frontend/public/downloads" -ForegroundColor Green
}

# Always refresh source zip via API path (desktop folder)
Write-Host "Done. Open /download on the site." -ForegroundColor Cyan
