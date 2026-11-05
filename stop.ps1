# Evolve — إيقاف موثوق على Windows (يشمل أيتام uvicorn --reload)
$ErrorActionPreference = "SilentlyContinue"
$Root = $PSScriptRoot
$portFile = Join-Path $Root "data\runtime-port.txt"
$apiPort = 7000
if (Test-Path $portFile) {
    $raw = (Get-Content $portFile -Raw).Trim()
    if ($raw -match '^\d+$') { $apiPort = [int]$raw }
}

Write-Host "Stopping Evolve on ports $apiPort and 3000..." -ForegroundColor Yellow

function Kill-Tree([int]$ProcId) {
    if (-not $ProcId -or $ProcId -eq 0) { return }
    Write-Host "  killing PID $ProcId"
    & taskkill.exe /PID $ProcId /T /F 2>$null | Out-Null
    Stop-Process -Id $ProcId -Force -ErrorAction SilentlyContinue
}

function Stop-PortTree([int]$Port) {
    $pids = @(
        Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue |
            Select-Object -ExpandProperty OwningProcess -Unique
    )
    foreach ($procId in $pids) { Kill-Tree $procId }
}

Stop-PortTree $apiPort
Stop-PortTree 3000

# Orphaned uvicorn --reload workers keep the socket after the parent dies.
# netstat may still show the dead parent PID; kill real python/node by command line.
$markers = @(
    "*uvicorn app.main:app*",
    "*multiprocessing.spawn*",
    "*$Root*uvicorn*",
    "*Desktop\Agent\backend*",
    "*next dev*",
    "*next-server*",
    "*Evolve API*"
)

Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | ForEach-Object {
    $cmd = $_.CommandLine
    if (-not $cmd) { return }
    foreach ($m in $markers) {
        if ($cmd -like $m) {
            # Only kill spawn workers that belong to Evolve (parent was our uvicorn)
            if ($m -eq "*multiprocessing.spawn*") {
                if ($cmd -notmatch "spawn_main") { return }
                # Prefer workers whose parent is gone or was on our API port
            }
            Kill-Tree $_.ProcessId
            break
        }
    }
}

# Extra pass: any python still bound conceptually — kill spawn_main orphans holding API
Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -match 'python' -and $_.CommandLine -match 'spawn_main\(parent_pid=' } |
    ForEach-Object { Kill-Tree $_.ProcessId }

$deadline = (Get-Date).AddSeconds(10)
while ((Get-Date) -lt $deadline) {
    $still = @(Get-NetTCPConnection -State Listen -LocalPort $apiPort, 3000 -ErrorAction SilentlyContinue)
    if (-not $still -or $still.Count -eq 0) { break }
    foreach ($c in $still) {
        Kill-Tree $c.OwningProcess
        # If OwningProcess is dead, hunt python spawn workers again
        Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
            Where-Object { $_.CommandLine -match 'spawn_main|uvicorn app\.main' } |
            ForEach-Object { Kill-Tree $_.ProcessId }
    }
    Start-Sleep -Milliseconds 400
}

$left = @(Get-NetTCPConnection -State Listen -LocalPort $apiPort, 3000 -ErrorAction SilentlyContinue)
if ($left.Count -gt 0) {
    Write-Host "WARNING: ports still busy: $($left.LocalPort -join ',')" -ForegroundColor Yellow
} else {
    Write-Host "Done." -ForegroundColor Green
}
