[CmdletBinding()]
param(
    [switch]$SkipMigrationDriftCheck
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$repositoryRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "../.."))

function Get-LocalResponse([string]$Uri, [string]$Label) {
    try {
        $response = Invoke-RestMethod -Uri $Uri -TimeoutSec 10
        if ($response.status -and $response.status -ne "ok") {
            throw "$Label returned status '$($response.status)'."
        }
        return $response
    } catch {
        throw "$Label is unavailable. Confirm the local backend is running."
    }
}

Push-Location $repositoryRoot
try {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw "Docker is not available on PATH."
    }
    & docker compose ps
    if ($LASTEXITCODE -ne 0) { throw "docker compose ps failed." }

    $health = Get-LocalResponse "http://localhost:8000/health" "Health"
    $ready = Get-LocalResponse "http://localhost:8000/health/ready" "Readiness"
    $release = Get-LocalResponse "http://localhost:8000/api/v1/release" "Release"
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
