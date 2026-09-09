[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("RESET-DEMO")]
    [string]$Confirmation,
    [switch]$SkipSafetyBackup
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$repositoryRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "../.."))

Push-Location $repositoryRoot
try {
    if (-not $SkipSafetyBackup) {
        & (Join-Path $PSScriptRoot "backup_db.ps1")
        if ($LASTEXITCODE -ne 0) { throw "Safety backup failed; demo reset was not started." }
    }

    & docker compose exec -T backend python -m scripts.seed_demo_data `
        --clear --confirm-clear CLEAR-DEMO-DATA
    if ($LASTEXITCODE -ne 0) { throw "Demo clear failed." }
    & docker compose exec -T backend python -m scripts.seed_demo_data
    if ($LASTEXITCODE -ne 0) { throw "Demo seed failed after clear." }

    Write-Host "Synthetic demo workspace reset completed. Non-demo investigations were not targeted."
} finally {
    Pop-Location
}
