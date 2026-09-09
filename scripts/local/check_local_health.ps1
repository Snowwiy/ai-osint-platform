[CmdletBinding()]
param([switch]$SkipMigrationDriftCheck)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$repositoryRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "../.."))

Push-Location $repositoryRoot
try {
    & docker compose ps
    if ($LASTEXITCODE -ne 0) { throw "docker compose ps failed." }

    $health = Invoke-RestMethod -Uri "http://localhost:8000/health"
    $ready = Invoke-RestMethod -Uri "http://localhost:8000/health/ready"
    $release = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/release"
    if ($health.status -ne "ok") { throw "Backend health is not ok." }
    if ($ready.status -ne "ok") { throw "Backend readiness is not ok." }

    if (-not $SkipMigrationDriftCheck) {
        & docker compose exec -T backend alembic check
        if ($LASTEXITCODE -ne 0) { throw "Alembic drift check failed." }
    }

    Write-Host "Health: $($health.status)"
    Write-Host "Readiness: $($ready.status)"
    Write-Host "Release: $($release.version)"
} finally {
    Pop-Location
}
