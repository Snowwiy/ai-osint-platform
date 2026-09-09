[CmdletBinding()]
param(
    [string]$OutputDirectory = "backups/local",
    [switch]$IncludeReports
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repositoryRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "../.."))
$destinationRoot = if ([IO.Path]::IsPathRooted($OutputDirectory)) {
    [IO.Path]::GetFullPath($OutputDirectory)
} else {
    [IO.Path]::GetFullPath((Join-Path $repositoryRoot $OutputDirectory))
}

Push-Location $repositoryRoot
try {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw "Docker is not available on PATH."
    }

    $postgresContainer = (& docker compose ps -q postgres).Trim()
    if (-not $postgresContainer) {
        throw "The local PostgreSQL service is not running. Run docker compose up -d first."
    }

    New-Item -ItemType Directory -Path $destinationRoot -Force | Out-Null
    $timestamp = Get-Date -Format "yyyyMMdd-HHmmss-fff"
    $dumpName = "raventech-$timestamp.dump"
    $containerDump = "/tmp/$dumpName"
    $databaseBackup = Join-Path $destinationRoot $dumpName
    if (Test-Path -LiteralPath $databaseBackup) {
        throw "Backup already exists: $databaseBackup"
    }

    try {
        & docker compose exec -T postgres pg_dump `
            -U raventech -d raventech --format=custom `
            --no-owner --no-privileges --file=$containerDump
        if ($LASTEXITCODE -ne 0) {
            throw "pg_dump failed with exit code $LASTEXITCODE."
        }
        & docker cp "${postgresContainer}:$containerDump" $databaseBackup
        if ($LASTEXITCODE -ne 0) {
            throw "docker cp failed with exit code $LASTEXITCODE."
        }
    } finally {
        & docker compose exec -T postgres rm -f $containerDump | Out-Null
    }

    $databaseSize = (Get-Item -LiteralPath $databaseBackup).Length
    if ($databaseSize -le 0) {
        throw "The database backup is empty: $databaseBackup"
    }
    Write-Host "Database backup created: $databaseBackup ($databaseSize bytes)"

    if ($IncludeReports) {
        $backendContainer = (& docker compose ps -q backend).Trim()
        if (-not $backendContainer) {
            throw "The backend service is required to back up report storage."
        }
        $reportsName = "raventech-reports-$timestamp.tar.gz"
        $containerReports = "/tmp/$reportsName"
        $reportsBackup = Join-Path $destinationRoot $reportsName
        try {
            & docker compose exec -T backend tar -czf $containerReports -C /data/reports .
            if ($LASTEXITCODE -ne 0) {
                throw "Report archive creation failed with exit code $LASTEXITCODE."
            }
            & docker cp "${backendContainer}:$containerReports" $reportsBackup
            if ($LASTEXITCODE -ne 0) {
                throw "Report archive copy failed with exit code $LASTEXITCODE."
            }
        } finally {
            & docker compose exec -T backend rm -f $containerReports | Out-Null
        }
        Write-Host "Report storage backup created: $reportsBackup"
    }

    Write-Host "Backups contain application data. Store them securely; no .env or secret file was included."
} finally {
    Pop-Location
}
