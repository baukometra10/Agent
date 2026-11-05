# ============================================================
# Evolve — bootstrap local student host (Ollama)
#   .\scripts\bootstrap-internal-host.ps1
#   .\scripts\bootstrap-internal-host.ps1 -Model qwen3.5:4b
# ============================================================
param(
    [string]$Model = "qwen3.5:4b",
    [string]$EvalModel = "qwen2.5:0.5b",
    [string]$BaseUrl = "http://127.0.0.1:11434"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$ollama = Get-Command ollama -ErrorAction SilentlyContinue
if (-not $ollama) {
    Write-Host "Ollama not found. Install from https://ollama.com/download then re-run." -ForegroundColor Red
    exit 1
}

Write-Host "==> Ensuring Ollama is serving..."
try {
    Invoke-RestMethod -Uri "$BaseUrl/api/tags" -TimeoutSec 2 | Out-Null
} catch {
    $exe = (Get-Command ollama).Source
    Start-Process -FilePath $exe -ArgumentList "serve" -WindowStyle Hidden
    Start-Sleep -Seconds 4
}

Write-Host "==> Ensuring models present (pull if needed)..."
& ollama list
foreach ($m in @($Model, $EvalModel)) {
    if (-not $m) { continue }
    $has = (& ollama list) | Select-String -SimpleMatch $m
    if (-not $has) {
        Write-Host "    pulling $m ..."
        & ollama pull $m
    }
}

$envPath = Join-Path $Root ".env"
if (Test-Path $envPath) {
    $text = Get-Content $envPath -Raw
    if ($text -notmatch "(?m)^INTERNAL_MODEL_BASE_URL=") {
        Add-Content $envPath "`nINTERNAL_MODEL_BASE_URL=$BaseUrl"
    } else {
        $text = $text -replace "(?m)^#?\s*INTERNAL_MODEL_BASE_URL=.*$", "INTERNAL_MODEL_BASE_URL=$BaseUrl"
        Set-Content $envPath $text -NoNewline
    }
    $text = Get-Content $envPath -Raw
    if ($text -notmatch "(?m)^INTERNAL_MODEL_NAME=") {
        Add-Content $envPath "`nINTERNAL_MODEL_NAME=$Model"
    } else {
        $text = $text -replace "(?m)^#?\s*INTERNAL_MODEL_NAME=.*$", "INTERNAL_MODEL_NAME=$Model"
        Set-Content $envPath $text -NoNewline
    }
    $text = Get-Content $envPath -Raw
    if ($text -notmatch "(?m)^INTERNAL_EVAL_MODEL_NAME=") {
        Add-Content $envPath "`nINTERNAL_EVAL_MODEL_NAME=$EvalModel"
    } else {
        $text = $text -replace "(?m)^#?\s*INTERNAL_EVAL_MODEL_NAME=.*$", "INTERNAL_EVAL_MODEL_NAME=$EvalModel"
        Set-Content $envPath $text -NoNewline
    }
    Write-Host "==> .env wired: base=$Model eval=$EvalModel @ $BaseUrl"
}

Write-Host "==> Done. Restart Evolve: .\stop.ps1; .\start.ps1"
Write-Host "    Then: .\scripts\check-internal-host.ps1"
