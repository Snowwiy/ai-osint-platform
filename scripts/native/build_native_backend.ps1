$ErrorActionPreference = 'Stop'
& python (Join-Path $PSScriptRoot 'build.py') backend
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
