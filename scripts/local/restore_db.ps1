[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$BackupPath,
    [string]$TargetDatabase = ("raventech_restore_" + (Get-Date -Format "yyyyMMdd_HHmmss"))
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repositoryRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "../.."))
$resolvedBackup = if ([IO.Path]::IsPathRooted($BackupPath)) {
    [IO.Path]::GetFullPath($BackupPath)
} else {
    [IO.Path]::GetFullPath((Join-Path (Get-Location) $BackupPath))
}
if (-not (Test-Path -LiteralPath $resolvedBackup -PathType Leaf)) {
    throw "Backup file not found: $resolvedBackup"
}
if ($TargetDatabase -notmatch '^[A-Za-z][A-Za-z0-9_]{0,62}$') {
    throw "TargetDatabase must be a PostgreSQL-safe name of 1-63 letters, numbers, or underscores."
}
if ($TargetDatabase -in @("raventech", "postgres", "template0", "template1")) {
    throw "Refusing to restore over a live or system database. Choose a new TargetDatabase."
}

Push-Location $repositoryRoot
try {
    $postgresContainer = (& docker compose ps -q postgres).Trim()
    if (-not $postgresContainer) {
        throw "The local PostgreSQL service is not running."
    }

    $existingOutput = & docker compose exec -T postgres psql -U raventech -d postgres `
        -tAc "SELECT 1 FROM pg_database WHERE datname = '$TargetDatabase';"
    $existing = ($existingOutput | Out-String).Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "Could not check the target database."
    }
    if ($existing -eq "1") {
        throw "Target database already exists. Nothing was overwritten: $TargetDatabase"
    }

    $containerBackup = "/tmp/restore-$([Guid]::NewGuid().ToString('N')).dump"
    try {
        & docker cp $resolvedBackup "${postgresContainer}:$containerBackup"
        if ($LASTEXITCODE -ne 0) {
            throw "Could not copy the backup into the PostgreSQL container."
        }
        & docker compose exec -T postgres pg_restore --list $containerBackup | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "Backup validation failed; no database was created."
        }

        & docker compose exec -T postgres createdb -U raventech --template=template0 $TargetDatabase
        if ($LASTEXITCODE -ne 0) {
            throw "Could not create target database $TargetDatabase."
        }
        & docker compose exec -T postgres pg_restore -U raventech `
            -d $TargetDatabase --no-owner --no-privileges --exit-on-error $containerBackup
        if ($LASTEXITCODE -ne 0) {
            throw "Restore failed. The new database was retained for inspection: $TargetDatabase"
        }
    } finally {
        & docker compose exec -T postgres rm -f $containerBackup | Out-Null
    }

    Write-Host "Restore completed into new database: $TargetDatabase"
    Write-Host "The live raventech database was not changed. Validate the restored database before any manual cutover."
} finally {
    Pop-Location
}
