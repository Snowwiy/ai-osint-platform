[CmdletBinding()]
param(
    [ValidateSet("frontend", "backend", "docs")]
    [string]$Target = "frontend"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$url = switch ($Target) {
    "frontend" { "http://localhost:5173" }
    "backend" { "http://localhost:8000" }
    "docs" { "http://localhost:8000/docs" }
}
Start-Process $url
Write-Host "Opened local ${Target}: $url"
