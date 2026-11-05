# Probe Evolve internal student host (OpenAI-compatible)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Api = "http://127.0.0.1:7000"
try {
    $r = Invoke-RestMethod -Uri "$Api/system/ownership/host" -TimeoutSec 10
    $r | ConvertTo-Json -Depth 6
    if (-not $r.configured) {
        Write-Host "`nSet INTERNAL_MODEL_BASE_URL in .env (Ollama example: http://127.0.0.1:11434)" -ForegroundColor Yellow
    } elseif (-not $r.reachable) {
        Write-Host "`nHost configured but not reachable. Start Ollama/vLLM then retry." -ForegroundColor Yellow
    } else {
        Write-Host "`nInternal host reachable." -ForegroundColor Green
    }
} catch {
    Write-Host "API not up. Run .\start.ps1 first. $_" -ForegroundColor Red
    exit 1
}
