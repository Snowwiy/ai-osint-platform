[CmdletBinding()]
param(
    [switch]$OpenFrontend
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$repositoryRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "../.."))
$frontendUrl = "http://localhost:5173"

function Invoke-LocalProbe([string]$Uri, [string]$Label) {
    try {
        $response = Invoke-RestMethod -Uri $Uri -TimeoutSec 10
        if ($response.status -and $response.status -ne "ok") {
            throw "$Label returned status '$($response.status)'."
        }
        Write-Host "${Label}: ok"
        return $response
    } catch {
        throw "$Label is unavailable. Start Docker services and check the local logs."
    }
}

Push-Location $repositoryRoot
try {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw "Docker is not available on PATH. Install Docker Desktop and retry."
    }

    & docker compose up -d postgres redis backend celery-worker
    if ($LASTEXITCODE -ne 0) { throw "Docker Compose could not start the local services." }

    & docker compose exec -T backend alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw "Database migrations could not be applied safely." }

    $ready = $false
    for ($attempt = 1; $attempt -le 30; $attempt++) {
        try {
            $probe = Invoke-RestMethod -Uri "http://localhost:8000/health/ready" -TimeoutSec 5
            if ($probe.status -eq "ok") { $ready = $true; break }
        } catch {}
        Start-Sleep -Seconds 2
    }
    if (-not $ready) { throw "Backend readiness did not become ok within 60 seconds." }

    Invoke-LocalProbe "http://localhost:8000/health" "Health"
    Invoke-LocalProbe "http://localhost:8000/health/ready" "Readiness"
    $release = Invoke-LocalProbe "http://localhost:8000/api/v1/release" "Release"
    Write-Host "Release version: $($release.version)"

    if ($OpenFrontend) {
        Start-Process $frontendUrl
        Write-Host "Opened local frontend: $frontendUrl"
    } else {
        Write-Host "Frontend is not started by this script. Run: cd frontend; npm run dev"
    }
} finally {
    Pop-Location
}
