# Expose local Spixa (API + UI) via Cloudflare quick tunnels.
# Prerequisites: API on 7000, UI on 3000, cloudflared on PATH.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Data = Join-Path $Root "data"
New-Item -ItemType Directory -Force -Path $Data | Out-Null

function Start-QuickTunnel([string]$LocalUrl, [string]$Name) {
  $out = Join-Path $Data "tunnel-$Name.out.log"
  $err = Join-Path $Data "tunnel-$Name.err.log"
  Remove-Item $out, $err -ErrorAction SilentlyContinue
  $p = Start-Process -FilePath "cloudflared" -ArgumentList @(
    "tunnel", "--url", $LocalUrl, "--no-autoupdate"
  ) -RedirectStandardOutput $out -RedirectStandardError $err -PassThru -WindowStyle Hidden
  $url = $null
  for ($i = 0; $i -lt 45; $i++) {
    Start-Sleep -Seconds 1
    $txt = ((Get-Content $out -Raw -ErrorAction SilentlyContinue) + (Get-Content $err -Raw -ErrorAction SilentlyContinue))
    if ($txt -match 'https://[a-z0-9-]+\.trycloudflare\.com') {
      $url = $Matches[0]
      break
    }
  }
  if (-not $url) { throw "No tunnel URL for $Name" }
  [pscustomobject]@{ Name = $Name; Pid = $p.Id; Url = $url }
}

Write-Host "==> API health" -ForegroundColor Cyan
$health = Invoke-RestMethod "http://127.0.0.1:7000/health" -TimeoutSec 5
if ($health.status -ne "ok") { throw "API not healthy on :7000" }

$api = Start-QuickTunnel "http://127.0.0.1:7000" "api"
Write-Host "API public: $($api.Url)" -ForegroundColor Green

$envLocal = Join-Path $Root "frontend\.env.local"
"NEXT_PUBLIC_API_URL=$($api.Url)" | Set-Content $envLocal -Encoding utf8
Write-Host "Wrote $envLocal" -ForegroundColor Yellow
Write-Host "Restart Next.js so it picks up NEXT_PUBLIC_API_URL, then re-run UI tunnel if needed." -ForegroundColor Yellow

$ui = Start-QuickTunnel "http://127.0.0.1:3000" "ui"
Write-Host "UI public: $($ui.Url)" -ForegroundColor Green

@"
UI=$($ui.Url)
API=$($api.Url)
API_PID=$($api.Pid)
UI_PID=$($ui.Pid)
"@ | Set-Content (Join-Path $Data "public-urls.txt") -Encoding utf8

Write-Host ""
Write-Host "Open: $($ui.Url)" -ForegroundColor Cyan
Write-Host "Keep this machine awake; tunnels die if cloudflared/API stop." -ForegroundColor DarkYellow
