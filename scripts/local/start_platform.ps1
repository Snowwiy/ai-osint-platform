[CmdletBinding()]
param(
    [switch]$OpenFrontend
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$frontendUrl = "http://localhost:5173"

function Test-RavenTechRepositoryRoot([string]$Candidate) {
    if ([string]::IsNullOrWhiteSpace($Candidate)) { return $null }
    try {
        $root = (Resolve-Path -LiteralPath $Candidate -ErrorAction Stop).Path
    } catch {
        return $null
    }
    $requiredFiles = @(
        "docker-compose.yml",
        "pyproject.toml",
        "frontend/package.json",
        "desktop/package.json",
        "scripts/local/start_platform.ps1",
        "scripts/local/stop_platform.ps1",
        "scripts/local/restart_platform.ps1",
        "scripts/local/check_platform.ps1",
        "scripts/local/open_platform.ps1"
    )
    foreach ($relative in $requiredFiles) {
        if (-not (Test-Path -LiteralPath ([IO.Path]::Combine($root, $relative)) -PathType Leaf)) {
            return $null
        }
    }
    if (-not (Test-Path -LiteralPath ([IO.Path]::Combine($root, "backend/app")) -PathType Container)) {
        return $null
    }
    return $root
}

function Resolve-RavenTechRepositoryRoot {
    $candidates = [Collections.Generic.List[string]]::new()
    if (-not [string]::IsNullOrWhiteSpace($env:RAVENTECH_VALIDATED_PROJECT_ROOT)) {
        $candidates.Add($env:RAVENTECH_VALIDATED_PROJECT_ROOT)
    }
    if (-not [string]::IsNullOrWhiteSpace($PSScriptRoot)) {
        $candidates.Add([IO.Path]::GetFullPath([IO.Path]::Combine($PSScriptRoot, "../..")))
    }
    if (-not [string]::IsNullOrWhiteSpace($PSCommandPath)) {
        $scriptDirectory = [IO.Path]::GetDirectoryName($PSCommandPath)
        if (-not [string]::IsNullOrWhiteSpace($scriptDirectory)) {
            $candidates.Add([IO.Path]::GetFullPath([IO.Path]::Combine($scriptDirectory, "../..")))
        }
    }
    $currentPath = (Get-Location).Path
    if (-not [string]::IsNullOrWhiteSpace($currentPath)) { $candidates.Add($currentPath) }

    foreach ($candidate in $candidates) {
        $resolved = Test-RavenTechRepositoryRoot $candidate
        if ($resolved) { return $resolved }
    }
    throw "RavenTech repository root could not be resolved. Validate the desktop project path or run this script from the repository root."
}

$repositoryRoot = Resolve-RavenTechRepositoryRoot

function Invoke-LocalProbe([string]$Uri, [string]$Label) {
    try {
        $response = Invoke-RestMethod -Uri $Uri -TimeoutSec 10
        $statusProperty = $response.PSObject.Properties["status"]
        if ($statusProperty -and $statusProperty.Value -ne "ok") {
            throw "$Label returned a non-ok status."
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
