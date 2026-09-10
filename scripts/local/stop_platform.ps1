[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$repositoryRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "../.."))

Push-Location $repositoryRoot
try {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw "Docker is not available on PATH."
    }
    & docker compose stop backend celery-worker postgres redis
    if ($LASTEXITCODE -ne 0) { throw "Docker Compose could not stop the local services." }
    Write-Host "Local platform services stopped. Data volumes were not removed."
} finally {
    Pop-Location
}
