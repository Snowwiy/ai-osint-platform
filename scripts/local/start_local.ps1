[CmdletBinding()]
param([switch]$StartFrontend)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$repositoryRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "../.."))

Push-Location $repositoryRoot
try {
    & docker compose up -d postgres redis backend celery-worker
    if ($LASTEXITCODE -ne 0) { throw "Docker Compose startup failed." }
    & docker compose exec -T backend alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw "Migration upgrade failed." }

    $ready = $false
    for ($attempt = 1; $attempt -le 20; $attempt++) {
        try {
            $response = Invoke-RestMethod -Uri "http://localhost:8000/health/ready"
            if ($response.status -eq "ok") { $ready = $true; break }
        } catch {}
        Start-Sleep -Seconds 2
    }
    if (-not $ready) { throw "Backend readiness did not become ok within 40 seconds." }

    & (Join-Path $PSScriptRoot "check_local_health.ps1")
    if ($StartFrontend) {
        $frontendPath = Join-Path $repositoryRoot "frontend"
        if (-not (Test-Path -LiteralPath (Join-Path $frontendPath "node_modules"))) {
            throw "Frontend dependencies are missing. Run npm install from frontend first."
        }
        $process = Start-Process npm.cmd -ArgumentList "run", "dev" `
            -WorkingDirectory $frontendPath -WindowStyle Hidden -PassThru
        Write-Host "Frontend started in the background (PID $($process.Id))."
    } else {
        Write-Host "Start the frontend with: cd frontend; npm run dev"
    }
} finally {
    Pop-Location
}
