# ============================================================
# Spixa — ملف التشغيل الرئيسي (Windows) — ثابت وموثوق
#
#   cd c:\Users\u4363\Desktop\Agent
#   .\start.ps1
#   .\stop.ps1   # للإيقاف
# ============================================================

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
Set-Location $Root

function Test-PortFree([int]$Port) {
    try {
        $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $Port)
        $listener.Start()
        $listener.Stop()
        return $true
    } catch {
        return $false
    }
}

function Test-ApiHealthy([int]$Port) {
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/health" -UseBasicParsing -TimeoutSec 2
        return ($r.StatusCode -eq 200 -and $r.Content -match '"status"\s*:\s*"ok"')
    } catch {
        return $false
    }
}

function Stop-Port([int]$Port) {
    $conns = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
    foreach ($c in $conns) {
        if ($c.OwningProcess) {
            Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue
        }
    }
}

function Get-PreferredApiPort {
    # Prefer fixed safe port (Hyper-V blocks ~7932-9031 including 8000)
    $preferred = 7000
    $envFile = Join-Path $Root ".env"
    if (Test-Path $envFile) {
        $line = Select-String -Path $envFile -Pattern '^\s*API_PORT\s*=\s*(\d+)' | Select-Object -First 1
        if ($line) { $preferred = [int]$line.Matches[0].Groups[1].Value }
    }
    # If preferred is in excluded Hyper-V band, force 7000
    if ($preferred -ge 7932 -and $preferred -le 9031) { $preferred = 7000 }
    return $preferred
}

Write-Host ""
Write-Host "  Spixa — reliable local start" -ForegroundColor Cyan
Write-Host ""

$ApiPort = Get-PreferredApiPort
$DbPath = Join-Path $Root "data\evolve.db"
$SqliteUri = ("sqlite+aiosqlite:///" + ($DbPath -replace "\\", "/"))
$SqliteSync = ("sqlite:///" + ($DbPath -replace "\\", "/"))
$PgUri = "postgresql+asyncpg://evolve:evolve@127.0.0.1:5432/evolve"
$PgSync = "postgresql://evolve:evolve@127.0.0.1:5432/evolve"
$Workspaces = Join-Path $Root "data\workspaces"
$RuntimePortFile = Join-Path $Root "data\runtime-port.txt"
$FrontendEnv = Join-Path $Root "frontend\.env.local"
$Logs = Join-Path $Root "data\logs"
New-Item -ItemType Directory -Force -Path (Join-Path $Root "data"), $Workspaces, $Logs | Out-Null

if (-not (Test-Path (Join-Path $Root ".env"))) {
    Copy-Item (Join-Path $Root ".env.example") (Join-Path $Root ".env")
}

# Prefer PostgreSQL + pgvector (strongest local DB). Fall back to SQLite if Docker unavailable.
$DbUri = $SqliteUri
$DbSync = $SqliteSync
$UsePostgres = $false
$dockerCmd = $null
foreach ($candidate in @(
    (Get-Command docker -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source),
    "$env:ProgramFiles\Docker\Docker\resources\bin\docker.exe",
    "$env:ProgramFiles\Docker\Docker\resources\bin\docker.EXE",
    "$env:LOCALAPPDATA\Programs\DockerDesktop\resources\bin\docker.exe",
    "$env:LOCALAPPDATA\Docker\wsl\docker-from-docker\docker.exe"
)) {
    if ($candidate -and (Test-Path $candidate)) { $dockerCmd = $candidate; break }
}
if ($dockerCmd) {
    # Ensure credential helpers (docker-credential-desktop) resolve for compose/pull.
    $dockerBin = Split-Path -Parent $dockerCmd
    if ($dockerBin -and ($env:Path -notlike "*$dockerBin*")) {
        $env:Path = "$dockerBin;$env:Path"
    }
    Write-Host "==> Ensuring PostgreSQL (pgvector) via Docker..." -ForegroundColor Green
    try {
        Push-Location $Root
        # Native docker stderr must not abort under $ErrorActionPreference=Stop
        $prevEap = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        & $dockerCmd compose up -d db 2>&1 | Out-Null
        $composeExit = $LASTEXITCODE
        $ErrorActionPreference = $prevEap
        Pop-Location
        $pgOk = $false
        if ($composeExit -eq 0 -or $composeExit -eq $null) {
            for ($i = 0; $i -lt 40; $i++) {
                Start-Sleep -Milliseconds 500
                try {
                    $client = [System.Net.Sockets.TcpClient]::new()
                    $iar = $client.BeginConnect("127.0.0.1", 5432, $null, $null)
                    $ok = $iar.AsyncWaitHandle.WaitOne(400)
                    if ($ok -and $client.Connected) { $pgOk = $true; $client.Close(); break }
                    $client.Close()
                } catch {}
            }
        }
        if ($pgOk) {
            $UsePostgres = $true
            $DbUri = $PgUri
            $DbSync = $PgSync
            Write-Host "    PostgreSQL ready on :5432" -ForegroundColor Green
        } else {
            Write-Host "    Postgres not ready (compose exit=$composeExit) — using SQLite fallback." -ForegroundColor Yellow
        }
    } catch {
        Write-Host "    Docker Postgres unavailable — using SQLite fallback. ($($_.Exception.Message))" -ForegroundColor Yellow
        Pop-Location -ErrorAction SilentlyContinue
    }
} else {
    Write-Host "==> Docker not found — using SQLite. Install Docker Desktop for PostgreSQL." -ForegroundColor Yellow
}

function Stop-EvolvePythonOrphans {
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object {
            $_.CommandLine -and (
                $_.CommandLine -like "*uvicorn app.main:app*" -or
                $_.CommandLine -match "spawn_main\(parent_pid="
            )
        } |
        ForEach-Object {
            Write-Host "  clearing orphan PID $($_.ProcessId)" -ForegroundColor Yellow
            & taskkill.exe /PID $_.ProcessId /T /F 2>$null | Out-Null
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        }
}

# Never silently reuse a zombie/orphan listener — clear Spixa API processes first.
Stop-EvolvePythonOrphans
if (-not (Test-PortFree $ApiPort)) {
    Write-Host "==> Freeing port $ApiPort..." -ForegroundColor Yellow
    Stop-Port $ApiPort
    Stop-EvolvePythonOrphans
    Start-Sleep -Seconds 2
}
if (-not (Test-PortFree $ApiPort)) {
    foreach ($alt in 7100, 7500, 7700, 9100, 9200, 18080) {
        if (Test-PortFree $alt) {
            Write-Host "==> Preferred port busy; using $alt" -ForegroundColor Yellow
            $ApiPort = $alt
            break
        }
    }
}

# Persist port for UI + stop.ps1 (prevents intermittent mismatch)
Set-Content -Path $RuntimePortFile -Value "$ApiPort" -NoNewline
@"
NEXT_PUBLIC_API_URL=http://127.0.0.1:$ApiPort
"@ | Set-Content -Path $FrontendEnv -Encoding utf8

# Sync root .env API URL/port + database so backends/tools agree
$envPath = Join-Path $Root ".env"
$envText = Get-Content $envPath -Raw
$envText = $envText -replace '(?m)^\s*API_PORT\s*=.*$', "API_PORT=$ApiPort"
$envText = $envText -replace '(?m)^\s*NEXT_PUBLIC_API_URL\s*=.*$', "NEXT_PUBLIC_API_URL=http://127.0.0.1:$ApiPort"
$envText = $envText -replace '(?m)^\s*DATABASE_URL\s*=.*$', "DATABASE_URL=$DbUri"
$envText = $envText -replace '(?m)^\s*DATABASE_URL_SYNC\s*=.*$', "DATABASE_URL_SYNC=$DbSync"
if ($envText -notmatch '(?m)^\s*API_PORT\s*=') { $envText += "`r`nAPI_PORT=$ApiPort`r`n" }
if ($envText -notmatch '(?m)^\s*NEXT_PUBLIC_API_URL\s*=') { $envText += "`r`nNEXT_PUBLIC_API_URL=http://127.0.0.1:$ApiPort`r`n" }
if ($envText -notmatch '(?m)^\s*DATABASE_URL\s*=') { $envText += "`r`nDATABASE_URL=$DbUri`r`n" }
if ($envText -notmatch '(?m)^\s*DATABASE_URL_SYNC\s*=') { $envText += "`r`nDATABASE_URL_SYNC=$DbSync`r`n" }
Set-Content -Path $envPath -Value $envText -Encoding utf8

$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$VenvPython = Join-Path $Backend ".venv\Scripts\python.exe"
$VenvUvicorn = Join-Path $Backend ".venv\Scripts\uvicorn.exe"

# Ensure latest schema (Venture / Twin / Patterns / Research tables)
Write-Host "==> Ensuring database tables..." -ForegroundColor Cyan
Push-Location $Backend
try {
    if (Test-Path $VenvPython) {
        & $VenvPython (Join-Path $Root "scripts\ensure-db-inline.py")
    }
} catch {
    Write-Host "    schema ensure skipped: $($_.Exception.Message)" -ForegroundColor Yellow
} finally {
    Pop-Location
}

if (-not (Test-Path $VenvPython)) {
    Write-Host "==> Creating Python venv..." -ForegroundColor Yellow
    Push-Location $Backend
    python -m venv .venv
    & .\.venv\Scripts\python.exe -m pip install -U pip
    & .\.venv\Scripts\pip.exe install -e ".[dev]"
    Pop-Location
}
if (-not (Test-Path $VenvUvicorn)) {
    Push-Location $Backend
    & .\.venv\Scripts\pip.exe install -e ".[dev]"
    Pop-Location
}
if (-not (Test-Path (Join-Path $Frontend "node_modules"))) {
    Write-Host "==> Installing frontend packages..." -ForegroundColor Yellow
    Push-Location $Frontend
    npm install
    Pop-Location
}

$ApiLog = Join-Path $Logs "api.log"
$UiLog = Join-Path $Logs "ui.log"

if (-not (Test-ApiHealthy $ApiPort)) {
    Write-Host "==> Starting API on http://127.0.0.1:$ApiPort ..." -ForegroundColor Green
    $apiArgs = @(
        "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
        @"
`$env:DATABASE_URL='$DbUri'
`$env:DATABASE_URL_SYNC='$DbSync'
`$env:WORKSPACES_ROOT='$Workspaces'
`$env:API_PORT='$ApiPort'
Set-Location '$Backend'
# No --reload: on Windows it orphans multiprocessing workers that keep the port.
& '$VenvUvicorn' app.main:app --host 127.0.0.1 --port $ApiPort *> '$ApiLog'
"@
    )
    Start-Process -FilePath "powershell" -ArgumentList $apiArgs -WindowStyle Minimized | Out-Null

    $ok = $false
    for ($i = 0; $i -lt 40; $i++) {
        Start-Sleep -Milliseconds 500
        if (Test-ApiHealthy $ApiPort) { $ok = $true; break }
    }
    if (-not $ok) {
        Write-Host "API failed to become healthy. Last log:" -ForegroundColor Red
        if (Test-Path $ApiLog) { Get-Content $ApiLog -Tail 40 }
        throw "API did not start on port $ApiPort"
    }
    Write-Host "    API healthy." -ForegroundColor Green
}

# Frontend
if (-not (Test-PortFree 3000)) {
    # If something is on 3000, free it for Spixa UI consistency
    Write-Host "==> Freeing port 3000 for UI..." -ForegroundColor Yellow
    Stop-Port 3000
    Start-Sleep -Seconds 1
}

Write-Host "==> Starting UI on http://localhost:3000 (API=$ApiPort)..." -ForegroundColor Green
$feArgs = @(
    "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
    @"
`$env:NEXT_PUBLIC_API_URL='http://127.0.0.1:$ApiPort'
Set-Location '$Frontend'
npm run dev -- --port 3000 *> '$UiLog'
"@
)
Start-Process -FilePath "powershell" -ArgumentList $feArgs -WindowStyle Minimized | Out-Null

$uiOk = $false
for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Milliseconds 500
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:3000" -UseBasicParsing -TimeoutSec 2
        if ($r.StatusCode -ge 200) { $uiOk = $true; break }
    } catch {}
}

Write-Host ""
if ($uiOk) {
    Write-Host "  جاهز ويعمل:" -ForegroundColor Green
} else {
    Write-Host "  API يعمل. الواجهة ما زالت تقلع — افتح بعد ثوانٍ." -ForegroundColor Yellow
    if (Test-Path $UiLog) { Write-Host "  UI log: $UiLog" }
}
Write-Host "    API : http://127.0.0.1:$ApiPort/docs"
Write-Host "    UI  : http://localhost:3000"
if ($UsePostgres) {
    Write-Host "    DB  : PostgreSQL (pgvector) @ 127.0.0.1:5432"
} else {
    Write-Host "    DB  : SQLite fallback"
}
Write-Host "    Stop: .\stop.ps1"
Write-Host ""
