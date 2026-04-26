# Stops the local ScreenPulse dev services tracked in .codex-run/dev-state.json.
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$statePath = Join-Path $repoRoot ".codex-run\dev-state.json"

if (-not (Test-Path $statePath)) {
    Write-Host "No saved ScreenPulse dev state found."
    exit 0
}

$state = Get-Content $statePath -Raw | ConvertFrom-Json
$stopped = @()

foreach ($serviceName in @("frontend", "backend", "admin_frontend")) {
    $service = $state.$serviceName
    if (-not $service -or -not $service.pid) {
        continue
    }

    $process = Get-Process -Id $service.pid -ErrorAction SilentlyContinue
    if ($process) {
        Stop-Process -Id $service.pid -Force
        $stopped += "${serviceName}:$($service.pid)"
    }
}

Remove-Item $statePath -Force -ErrorAction SilentlyContinue

if ($stopped.Count -eq 0) {
    Write-Host "No tracked ScreenPulse dev processes were running."
} else {
    Write-Host ("Stopped " + ($stopped -join ", "))
}
