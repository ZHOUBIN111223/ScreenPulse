# Starts the local ScreenPulse frontend and backend on the repo's default dev ports.
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

function Wait-ForPort {
    param(
        [Parameter(Mandatory = $true)]
        [int]$Port,
        [int]$TimeoutSeconds = 30
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        $listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
            Select-Object -First 1
        if ($listener) {
            return $listener.OwningProcess
        }
        Start-Sleep -Milliseconds 500
    } while ((Get-Date) -lt $deadline)

    throw "Port $Port did not start listening within $TimeoutSeconds seconds."
}

function Wait-ForUrl {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Url,
        [int]$TimeoutSeconds = 45
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        try {
            Invoke-WebRequest -UseBasicParsing $Url -TimeoutSec 5 | Out-Null
            return
        } catch {
            Start-Sleep -Milliseconds 500
        }
    } while ((Get-Date) -lt $deadline)

    throw "URL $Url did not become ready within $TimeoutSeconds seconds."
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$stateDir = Join-Path $repoRoot ".codex-run"
$statePath = Join-Path $stateDir "dev-state.json"
$backendPort = 8011
$frontendPort = 3001
$backendUrl = "http://127.0.0.1:$backendPort"
$frontendUrl = "http://127.0.0.1:$frontendPort"

New-Item -ItemType Directory -Force $stateDir | Out-Null

$stopScript = Join-Path $PSScriptRoot "stop-dev.ps1"
if (Test-Path $stopScript) {
    & $stopScript | Out-Null
    Start-Sleep -Seconds 1
}

foreach ($port in @($backendPort, $frontendPort)) {
    $listeners = @(Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
    if ($listeners.Count -gt 0) {
        $pids = ($listeners | Select-Object -ExpandProperty OwningProcess -Unique) -join ", "
        throw "Port $port is already in use by PID(s): $pids"
    }
}

$backendPython = Join-Path $repoRoot "backend\.venv\Scripts\python.exe"
$frontendNextBin = Join-Path $repoRoot "frontend\node_modules\next\dist\bin\next"

if (-not (Test-Path $backendPython)) {
    throw "Missing backend virtualenv at $backendPython"
}
if (-not (Test-Path $frontendNextBin)) {
    throw "Missing Next.js entry at $frontendNextBin"
}

$nodeCommand = (Get-Command node -ErrorAction Stop).Source
$cmdCommand = Join-Path $env:SystemRoot "System32\cmd.exe"
$backendLog = Join-Path $stateDir "backend-8011.log"
$backendErrLog = Join-Path $stateDir "backend-8011.err.log"
$frontendLog = Join-Path $stateDir "frontend-3001.log"
$frontendErrLog = Join-Path $stateDir "frontend-3001.err.log"

foreach ($path in @($backendLog, $backendErrLog, $frontendLog, $frontendErrLog)) {
    Remove-Item $path -Force -ErrorAction SilentlyContinue
}

Start-Process `
    -FilePath $backendPython `
    -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$backendPort") `
    -WorkingDirectory (Join-Path $repoRoot "backend") `
    -RedirectStandardOutput $backendLog `
    -RedirectStandardError $backendErrLog | Out-Null

$frontendCommand = "set NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:$backendPort/api&& `"$nodeCommand`" `"$frontendNextBin`" dev --hostname 127.0.0.1 --port $frontendPort"
Start-Process `
    -FilePath $cmdCommand `
    -ArgumentList @("/c", $frontendCommand) `
    -WorkingDirectory (Join-Path $repoRoot "frontend") `
    -RedirectStandardOutput $frontendLog `
    -RedirectStandardError $frontendErrLog | Out-Null

$backendPid = Wait-ForPort -Port $backendPort
$frontendPid = Wait-ForPort -Port $frontendPort

Wait-ForUrl -Url "$backendUrl/"
Wait-ForUrl -Url $frontendUrl

$state = [ordered]@{
    saved_at = (Get-Date).ToString("o")
    ports = [ordered]@{
        backend = $backendPort
        frontend = $frontendPort
    }
    backend = [ordered]@{
        pid = $backendPid
        url = $backendUrl
        docs_url = "$backendUrl/docs"
        log = $backendLog
        error_log = $backendErrLog
    }
    frontend = [ordered]@{
        pid = $frontendPid
        url = $frontendUrl
        api_base_url = "http://127.0.0.1:$backendPort/api"
        log = $frontendLog
        error_log = $frontendErrLog
    }
}

$state | ConvertTo-Json -Depth 6 | Set-Content -Path $statePath -Encoding utf8

Write-Host "ScreenPulse dev stack is running."
Write-Host "Frontend: $frontendUrl"
Write-Host "Backend:  $backendUrl"
Write-Host "State:    $statePath"
