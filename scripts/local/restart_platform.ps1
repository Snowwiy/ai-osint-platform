[CmdletBinding()]
param(
    [switch]$OpenFrontend
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

& (Join-Path $PSScriptRoot "stop_platform.ps1")
if ($LASTEXITCODE -ne 0) { throw "Local platform stop failed; restart was not attempted." }
& (Join-Path $PSScriptRoot "start_platform.ps1") -OpenFrontend:$OpenFrontend
if ($LASTEXITCODE -ne 0) { throw "Local platform start failed." }
